"""WhatsApp personal reply agent: contact-specific style + timed, policy-gated auto-reply.

Live pipeline (see docs/WHATSAPP_PERSONAL_REPLY_AGENT.md):

    incoming event -> own message? (learn, never reply) -> GROUP? (ignore, structural)
    -> placeholder / undecrypted? (PENDING_DECRYPTION, wait for the real body)
    -> claim message_id (persistent dedupe) -> AutoReplyPolicy (grant / base mode / expiry)
    -> short coalescing window -> profile + recent thread + top-K owner examples
    -> local LLM -> quality gate -> AUTO / ASK / SUGGEST -> re-check expiry & STOP
    -> ActionLedger (PREPARED -> STARTED -> VERIFIED | FAILED | UNCERTAIN) -> send -> verify

The agent holds no ToolRegistry: an incoming message can only ever produce a text reply to the
same direct chat it came from.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Iterable, Optional

from jarvis.integrations.whatsapp.personal_reply import importer as imp
from jarvis.integrations.whatsapp.personal_reply import style_analyzer
from jarvis.integrations.whatsapp.personal_reply.auto_reply_policy import AutoReplyPolicy, PolicyDecision
from jarvis.integrations.whatsapp.personal_reply.context_builder import build as build_context
from jarvis.integrations.whatsapp.personal_reply.dedupe import is_group_chat, is_placeholder
from jarvis.integrations.whatsapp.personal_reply.example_index import ContactExampleIndex, embed
from jarvis.integrations.whatsapp.personal_reply.models import (
    ChatLine, ContactStyleProfile, Direction, ExampleSource, GrantScope, IncomingBatch, Outcome, ReplyExample, ReplyMode,
)
from jarvis.integrations.whatsapp.personal_reply.quality_gate import evaluate, has_ai_phrases
from jarvis.integrations.whatsapp.personal_reply.reply_generator import ReplyGenerator
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore, text_hash
from jarvis.integrations.whatsapp.personal_reply.understand import understand

logger = logging.getLogger("jarvis.whatsapp.personal_reply")

MIN_PROFILE_CONFIDENCE_AUTO = 0.35
FEEDBACK = {
    "looks_right": {},
    "too_formal": {"formality_shift": -1},
    "too_casual": {"formality_shift": +1},
    "more_english": {"tanglish_shift": -0.15},
    "more_tanglish": {"tanglish_shift": +0.15},
    "shorter": {"length_factor": 0.75},
    "longer": {"length_factor": 1.3},
}


def _fmt_until(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%I:%M %p").lstrip("0")


def _duration_words(seconds: float) -> str:
    mins = max(1, round(seconds / 60))
    if mins % 60 == 0:
        h = mins // 60
        return f"{h} hour{'s' if h != 1 else ''}"
    if mins > 60:
        return f"{mins // 60} h {mins % 60} min"
    return f"{mins} minute{'s' if mins != 1 else ''}"


class PersonalReplyAgent:
    def __init__(self, store: Optional[PersonalReplyStore] = None, transport: Any = None, inbox: Any = None,
                 generator: Optional[ReplyGenerator] = None, policy: Optional[AutoReplyPolicy] = None, ledger: Any = None,
                 policy_evaluator: Any = None, event_bus: Any = None, coalesce_s: float = 1.2,
                 owner_names: Iterable[str] = (), clock: Callable[[], float] = time.time, use_jde: bool = True,
                 auto_reply_untrained: bool = False, notifier: Optional[Callable[[str], Any]] = None) -> None:
        self.store = store or PersonalReplyStore()
        self.transport = transport
        self._inbox = inbox
        self.generator = generator or ReplyGenerator()
        self.policy = policy or AutoReplyPolicy(self.store, auto_reply_untrained=auto_reply_untrained)
        self.ledger = ledger
        self.policy_evaluator = policy_evaluator
        self.event_bus = event_bus
        self.coalesce_s = coalesce_s
        self.owner_names = [n for n in owner_names if n]
        self.clock = clock
        self.use_jde = use_jde
        self.notifier = notifier
        self.index = ContactExampleIndex(self.store)
        self._buffers: dict[str, IncomingBatch] = {}
        self._flush_tasks: dict[str, asyncio.Task] = {}
        self._owner_replied_at: dict[str, float] = {}
        self._last_contact: str = ""
        self._background: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ helpers
    @property
    def inbox(self):
        if self._inbox is None:
            from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
            self._inbox = WhatsAppInbox.get_default()
        return self._inbox

    def _emit(self, name: str, **data: Any) -> None:
        if self.event_bus is not None:
            try:
                self.event_bus.emit(f"whatsapp.personal.{name}", data.get("contact_id", ""), **data)
            except Exception:
                pass

    def _activity(self, contact_id: str, name: str, stage: str, detail: str = "") -> None:
        row = self.store.activity(contact_id, name, stage, detail)
        self._emit("activity", **row)

    async def _notify(self, text: str) -> None:
        if self.notifier is None:
            return
        try:
            res = self.notifier(text)
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            pass

    def profile_for(self, contact_id: str) -> tuple[ContactStyleProfile, bool]:
        """Person-specific profile, else the owner's default style (never another person's profile)."""
        prof = self.store.load_profile(contact_id)
        if prof is not None and prof.messages_analyzed > 0:
            return prof, True
        default = self.store.load_profile("__default__")
        if default is not None:
            fallback = ContactStyleProfile.from_dict({**default.to_dict(), "contact_id": contact_id,
                                                      "display_name": self.store.display_name(contact_id)})
            return fallback, False
        return ContactStyleProfile(contact_id=contact_id, display_name=self.store.display_name(contact_id),
                                   preferred_language="ENGLISH", formality="CASUAL", median_message_length=8,
                                   typical_reply_length="1 short sentence"), False

    # ------------------------------------------------------------------ live pipeline
    async def handle_incoming(self, message: Any) -> dict[str, Any]:
        chat_id = getattr(message, "chat_id", "") or ""
        mid = getattr(message, "message_id", "") or ""
        if getattr(message, "is_from_me", False):
            return self.learn_owner_message(message)
        if is_group_chat(chat_id):
            return {"status": Outcome.IGNORED_GROUP.value}  # structural gate: no model, no reply, ever
        name = getattr(message, "sender_display_name", "") or chat_id.split("@")[0]
        if is_placeholder(message):
            if self.store.mark_pending_decryption(mid, chat_id):
                self._activity(chat_id, name, "Waiting for message", "not decrypted yet - no reply")
            return {"status": Outcome.PENDING_DECRYPTION.value, "message_id": mid}
        if not mid or not self.store.claim(mid, chat_id):
            return {"status": Outcome.DUPLICATE.value, "message_id": mid}
        self.store.upsert_contact(chat_id, name)
        self._last_contact = chat_id
        text = (getattr(message, "text", "") or "").strip()
        if self.store.load_profile(chat_id) is not None:
            self.store.add_sources(chat_id, [ChatLine(timestamp=self.clock(), sender=name, direction=Direction.CONTACT,
                                                      text=text, message_id=mid)], import_id="live")
        profile_exists = self.store.load_profile(chat_id) is not None
        decision = self.policy.decide(chat_id, chat_id, has_profile=profile_exists, now=self.clock())
        if decision.mode == ReplyMode.OFF:
            self.store.set_processed_state(mid, "DONE")
            return {"status": Outcome.NOT_ENABLED.value, "reason": decision.reason}
        self._activity(chat_id, name, "Incoming", decision.mode.value)
        batch = self._buffers.get(chat_id)
        if batch is None:
            batch = IncomingBatch(contact_id=chat_id, chat_id=chat_id, display_name=name, message_ids=[], texts=[],
                                  received_at=self.clock())
            self._buffers[chat_id] = batch
        batch.message_ids.append(mid)
        batch.texts.append(text)
        if self.coalesce_s <= 0:
            return await self._flush(chat_id)
        task = self._flush_tasks.get(chat_id)
        if task and not task.done():
            task.cancel()
        self._flush_tasks[chat_id] = asyncio.create_task(self._delayed_flush(chat_id))
        return {"status": Outcome.QUEUED.value, "message_id": mid}

    async def _delayed_flush(self, chat_id: str) -> None:
        try:
            await asyncio.sleep(self.coalesce_s)
        except asyncio.CancelledError:
            return
        try:
            await self._flush(chat_id)
        except Exception:
            logger.exception("Personal reply failed for %s", chat_id)

    async def _flush(self, chat_id: str) -> dict[str, Any]:
        batch = self._buffers.pop(chat_id, None)
        self._flush_tasks.pop(chat_id, None)
        if batch is None or not batch.message_ids:
            return {"status": Outcome.DUPLICATE.value}
        try:
            return await self.process_batch(batch)
        finally:
            for mid in batch.message_ids:
                self.store.set_processed_state(mid, "DONE")

    async def process_batch(self, batch: IncomingBatch) -> dict[str, Any]:
        cid, name = batch.contact_id, batch.display_name
        stop_gen = self.policy.stop_generation
        prof_exists = self.store.load_profile(cid) is not None
        decision = self.policy.decide(cid, batch.chat_id, has_profile=prof_exists, now=self.clock())
        if decision.mode == ReplyMode.OFF:
            return {"status": Outcome.NOT_ENABLED.value if decision.reason != "GROUP_BLOCKED" else Outcome.IGNORED_GROUP.value}
        if self._owner_replied_at.get(cid, 0) > batch.received_at:
            self._activity(cid, name, "Skipped", "you replied yourself")
            return {"status": Outcome.OWNER_REPLIED.value}
        reply_id = self.store.start_reply(batch.last_message_id, batch.message_ids, cid, batch.chat_id, decision.mode.value,
                                          decision.grant.grant_id if decision.grant else None, batch.text)
        if reply_id is None:
            return {"status": Outcome.DUPLICATE.value}
        self._activity(cid, name, "Analyzing")
        draft = await self.draft(cid, batch.texts, exclude_message_ids=set(batch.message_ids), name=name)
        cand, quality, profile, ctx, und = draft["candidate"], draft["quality"], draft["profile"], draft["context"], draft["understanding"]
        self._activity(cid, name, "Style", f"{ctx.target_language.title()}/{profile.effective_formality().replace('_', ' ').title()}")
        if cand is None:
            self.store.update_reply(reply_id, status=Outcome.NEEDS_USER_REVIEW.value, reason="reply model unavailable")
            self._activity(cid, name, "NOT SENT", "needs review (model unavailable)")
            await self._notify(f"New WhatsApp message from {name} needs your reply.")
            return {"status": Outcome.NEEDS_USER_REVIEW.value, "reply_id": reply_id, "reason": "model unavailable"}
        self.store.update_reply(reply_id, text=cand.text, draft_hash=text_hash(cand.text), quality=quality.to_dict())
        self._activity(cid, name, "Draft generated")
        reasons = list(quality.reasons)
        if und.requests_pc_action:
            reasons.append("asks for files or actions - conversation reply only")
        if und.confidence < 0.5 or und.intent in ("EMPTY", "UNCLEAR"):
            reasons.append("could not understand the message")
        if decision.mode == ReplyMode.SUGGEST_ONLY:
            self.store.update_reply(reply_id, status=Outcome.SUGGESTED.value, reason="; ".join(reasons)[:300])
            self._emit("suggestion", contact_id=cid, reply_id=reply_id, display_name=name, text=cand.text)
            self._activity(cid, name, "Suggested", "not sent (suggest only)")
            return {"status": Outcome.SUGGESTED.value, "reply_id": reply_id, "text": cand.text, "quality": quality.to_dict()}
        if decision.mode == ReplyMode.ASK_BEFORE_SEND:
            self.store.update_reply(reply_id, status=Outcome.AWAITING_APPROVAL.value, reason="; ".join(reasons)[:300])
            self._emit("approval_needed", contact_id=cid, reply_id=reply_id, display_name=name, text=cand.text)
            self._activity(cid, name, "Waiting for your OK")
            await self._notify(f"Draft reply to {name} is ready for your approval.")
            return {"status": Outcome.AWAITING_APPROVAL.value, "reply_id": reply_id, "text": cand.text, "quality": quality.to_dict()}
        # AUTO_REPLY_UNTIL
        if profile.confidence < MIN_PROFILE_CONFIDENCE_AUTO and draft["has_profile"]:
            reasons.append("style profile confidence too low")
        if reasons:
            self.store.update_reply(reply_id, status=Outcome.NEEDS_USER_REVIEW.value, reason="; ".join(reasons)[:300])
            self._emit("review_needed", contact_id=cid, reply_id=reply_id, display_name=name, text=cand.text, reasons=reasons)
            self._activity(cid, name, "NOT SENT", "needs review: " + "; ".join(reasons)[:120])
            await self._notify(f"WhatsApp reply to {name} was held for your review.")
            return {"status": Outcome.NEEDS_USER_REVIEW.value, "reply_id": reply_id, "text": cand.text, "reasons": reasons,
                    "quality": quality.to_dict()}
        if self._owner_replied_at.get(cid, 0) > batch.received_at:
            self.store.update_reply(reply_id, status=Outcome.OWNER_REPLIED.value)
            return {"status": Outcome.OWNER_REPLIED.value}
        if not self.policy.still_allowed(decision, stop_gen, now=self.clock()):
            self.store.update_reply(reply_id, status=Outcome.EXPIRED.value, reason="auto-reply ended or was stopped before sending")
            self._activity(cid, name, "NOT SENT", "auto-reply ended")
            return {"status": Outcome.EXPIRED.value, "reply_id": reply_id}
        return await self._send(reply_id, cid, batch.chat_id, name, cand.text, decision, batch.last_message_id)

    async def draft(self, contact_id: str, texts: list[str], exclude_message_ids: set[str] | None = None,
                    name: str = "") -> dict[str, Any]:
        """Everything short of sending: used by the live pipeline, Test Reply and Preview Style."""
        profile, has_profile = self.profile_for(contact_id)
        current = "\n".join(t for t in texts if t)
        und = understand(current, use_jde=self.use_jde)
        thread = self._thread(contact_id, exclude_message_ids or set())
        examples = self.index.retrieve(contact_id, current, k=6) if has_profile else []
        ctx = build_context(contact_id, name or self.store.display_name(contact_id), profile, thread, examples, texts)
        owner_ai = any(has_ai_phrases(e.example.reply) for e in examples)
        cand = await self.generator.generate(ctx, profile, owner_uses_ai_phrases=owner_ai)
        quality = None
        if cand is not None:
            copied = self.index.copied_reply_similarity(contact_id, cand.text, current) if has_profile else None
            quality = evaluate(cand, current, ctx.thread_text, ctx.example_text, profile, ctx.target_language,
                               owner_uses_ai_phrases=owner_ai, copied_example_similarity=copied)
        return {"candidate": cand, "quality": quality, "profile": profile, "context": ctx, "understanding": und,
                "has_profile": has_profile, "examples": examples}

    def _thread(self, chat_id: str, exclude: set[str], limit: int = 10) -> list[tuple[bool, str]]:
        try:
            msgs = self.inbox.get_chat_history(chat_id, limit=limit + len(exclude))
        except Exception:
            return []
        out = []
        for m in msgs:
            if m.chat_id != chat_id or m.message_id in exclude or not m.text or is_placeholder(m):
                continue
            out.append((bool(m.is_from_me), m.text))
        return out[-limit:]

    # ------------------------------------------------------------------ sending (ledger-backed, never blind resend)
    async def _send(self, reply_id: int, contact_id: str, chat_id: str, name: str, text: str, decision: Optional[PolicyDecision],
                    incoming_message_id: str) -> dict[str, Any]:
        if is_group_chat(chat_id) or chat_id != contact_id:
            self.store.update_reply(reply_id, status=Outcome.FAILED.value, reason="recipient identity not a single direct chat")
            return {"status": Outcome.AMBIGUOUS_CONTACT.value, "reply_id": reply_id}
        if self.transport is None:
            self.store.update_reply(reply_id, status=Outcome.FAILED.value, reason="no WhatsApp transport")
            return {"status": Outcome.FAILED.value, "reply_id": reply_id}
        if not self._policy_allows_send(decision):
            self.store.update_reply(reply_id, status=Outcome.NEEDS_USER_REVIEW.value, reason="blocked by policy")
            return {"status": Outcome.NEEDS_USER_REVIEW.value, "reply_id": reply_id}
        fingerprint = f"wa_personal_reply:{incoming_message_id}"
        action_id = f"wa_pr_{uuid.uuid4().hex[:12]}"
        ledger = self.ledger
        from jarvis.tools.base import IdempotencyClass, RiskLevel
        if ledger is not None:
            from jarvis.security.ledger.models import LedgerState
            dup, entry = ledger.check_duplicate(fingerprint)
            if dup:
                status = Outcome.UNCERTAIN.value if entry and entry.status in (LedgerState.STARTED, LedgerState.UNCERTAIN) else Outcome.DUPLICATE.value
                self.store.update_reply(reply_id, status=status, reason="already attempted - not resent")
                return {"status": status, "reply_id": reply_id}
            ledger.prepare_action(action_id=action_id, fingerprint=fingerprint, request_id=incoming_message_id,
                                  graph_id="whatsapp_personal_reply", node_id=str(reply_id), tool="send_whatsapp_message",
                                  risk=RiskLevel.EXTERNAL_EFFECT, idempotency=IdempotencyClass.NON_IDEMPOTENT,
                                  args_hash=text_hash(f"{chat_id}|{text}"), method="whatsapp",
                                  confirmation_ticket=decision.grant.grant_id if decision and decision.grant else "owner_approval",
                                  idempotency_key=fingerprint)
            if not ledger.start_action(action_id, fingerprint, RiskLevel.EXTERNAL_EFFECT, idempotency_key=fingerprint):
                self.store.update_reply(reply_id, status=Outcome.DUPLICATE.value, reason="another worker claimed this send")
                return {"status": Outcome.DUPLICATE.value, "reply_id": reply_id}
        started = self.clock()
        self.store.update_reply(reply_id, status="SENDING", final_hash=text_hash(text.strip()), text=text,
                                ledger_action_id=action_id if ledger is not None else None, send_started=started)
        try:
            ack = await asyncio.wait_for(self.transport.send_text(to=chat_id, text=text), timeout=30.0)
        except ConnectionError as exc:  # transport refused before anything left the PC
            return self._finish(reply_id, action_id, fingerprint, Outcome.FAILED, f"not connected: {exc}", contact_id, name)
        except Exception as exc:  # timeout / unknown: the message MAY have been sent - never resend blindly
            return self._finish(reply_id, action_id, fingerprint, Outcome.UNCERTAIN, f"{type(exc).__name__}: {exc}", contact_id, name)
        ack = ack or {}
        # fake transport: {"message_id": ...}; Baileys bridge: {"success": true, "result": {"message_id": ...}}
        sent_id = str(ack.get("message_id") or (ack.get("result") or {}).get("message_id") or "")
        if ack.get("success") is False or ack.get("error"):
            err = str(ack.get("error") or "send failed")
            outcome = Outcome.UNCERTAIN if "timed out" in err.lower() else Outcome.FAILED
            return self._finish(reply_id, action_id, fingerprint, outcome, err, contact_id, name)
        if not sent_id:
            return self._finish(reply_id, action_id, fingerprint, Outcome.UNCERTAIN, "no delivery acknowledgement", contact_id, name)
        self.store.update_reply(reply_id, sent_message_id=sent_id)
        self._activity(contact_id, name, "Sent")
        try:
            self.inbox.mark_as_replied(chat_id)
        except Exception:
            pass
        return self._finish(reply_id, action_id, fingerprint, Outcome.VERIFIED, "", contact_id, name, sent_id=sent_id, text=text)

    def _finish(self, reply_id: int, action_id: str, fingerprint: str, outcome: Outcome, reason: str, contact_id: str,
                name: str, sent_id: str = "", text: str = "") -> dict[str, Any]:
        now = self.clock()
        self.store.update_reply(reply_id, status=outcome.value, reason=reason[:300],
                                send_verified=now if outcome == Outcome.VERIFIED else None)
        if self.ledger is not None:
            from jarvis.security.ledger.models import LedgerState
            from jarvis.tools.base import RiskLevel
            state = {Outcome.VERIFIED: LedgerState.VERIFIED, Outcome.FAILED: LedgerState.FAILED}.get(outcome, LedgerState.UNCERTAIN)
            try:
                self.ledger.record_outcome(action_id, fingerprint, RiskLevel.EXTERNAL_EFFECT, state,
                                           verification_json=json.dumps({"sent_message_id": sent_id}), error_class=reason or None)
            except Exception:
                logger.debug("ledger outcome not recorded", exc_info=True)
        if outcome == Outcome.VERIFIED:
            self._activity(contact_id, name, "Verified")
        else:
            self._activity(contact_id, name, "NOT SENT" if outcome == Outcome.FAILED else "UNCERTAIN",
                           reason[:120] or outcome.value)
        self._emit("reply", contact_id=contact_id, reply_id=reply_id, status=outcome.value)
        return {"status": outcome.value, "reply_id": reply_id, "text": text, "sent_message_id": sent_id, "reason": reason}

    def _policy_allows_send(self, decision: Optional[PolicyDecision]) -> bool:
        """Phase 5 policy stays authoritative: DENY / PAUSE always wins; CONFIRM is satisfied only by an
        explicit owner grant (auto mode) or an explicit owner approval (decision None)."""
        if self.policy_evaluator is None:
            return True
        try:
            from jarvis.security.policy.models import PolicyDecisionType
            from jarvis.tools.system.whatsapp_tools import SendWhatsAppMessageTool
            verdict = self.policy_evaluator.evaluate_node(SendWhatsAppMessageTool.definition, {"message": "", "recipient": ""})
            if verdict.decision in (PolicyDecisionType.DENY, PolicyDecisionType.PAUSE_FOR_USER):
                return False
            if verdict.decision == PolicyDecisionType.REQUIRE_CONFIRMATION:
                return decision is None or (decision.grant is not None and decision.grant.granted_by_user)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ owner actions on drafts
    async def approve_reply(self, reply_id: int, edited_text: Optional[str] = None, mark_good: bool = False) -> dict[str, Any]:
        row = self.store.reply(reply_id)
        if row is None:
            return {"status": "NOT_FOUND"}
        if row["status"] not in (Outcome.SUGGESTED.value, Outcome.AWAITING_APPROVAL.value, Outcome.NEEDS_USER_REVIEW.value):
            return {"status": row["status"], "reason": "not waiting for approval"}
        text = (edited_text or row["text"] or "").strip()
        if not text:
            return {"status": "EMPTY"}
        if edited_text and edited_text.strip() != (row["text"] or "").strip():
            self._learn_example(row["contact_id"], row["incoming"], text, ExampleSource.USER_EDITED)
        elif mark_good:
            self._learn_example(row["contact_id"], row["incoming"], text, ExampleSource.APPROVED)
        name = self.store.display_name(row["contact_id"])
        return await self._send(reply_id, row["contact_id"], row["chat_id"], name, text, None, row["incoming_message_id"])

    def reject_reply(self, reply_id: int) -> dict[str, Any]:
        self.store.update_reply(reply_id, status="REJECTED")
        return {"status": "REJECTED"}

    # ------------------------------------------------------------------ learning (owner-authored text only)
    def learn_owner_message(self, message: Any) -> dict[str, Any]:
        chat_id = getattr(message, "chat_id", "") or ""
        text = (getattr(message, "text", "") or "").strip()
        mid = getattr(message, "message_id", "") or ""
        if is_group_chat(chat_id) or not text or is_placeholder(message):
            return {"status": Outcome.IGNORED_OWN.value}
        if self.store.is_sent_reply(chat_id, sent_message_id=mid, text=text):
            # JARVIS's own reply echoed back from the phone: not the owner replying, never style training data
            return {"status": Outcome.IGNORED_OWN.value, "reason": "JARVIS's own reply is never style training data"}
        self._owner_replied_at[chat_id] = self.clock()
        pending = self._flush_tasks.pop(chat_id, None)
        if pending and not pending.done():
            pending.cancel()  # the owner answered manually: JARVIS must not answer too
            self._buffers.pop(chat_id, None)
        if self.store.load_profile(chat_id) is None:
            return {"status": Outcome.IGNORED_OWN.value, "reason": "no profile for this contact"}
        self.store.add_sources(chat_id, [ChatLine(timestamp=self.clock(), sender="owner", direction=Direction.USER,
                                                  text=text, message_id=mid)], import_id="live")
        context = [t for mine, t in self._thread(chat_id, {mid}, limit=6) if not mine][-3:]
        if context:
            self._learn_example(chat_id, "\n".join(context), text, ExampleSource.LIVE_USER)
        return {"status": Outcome.IGNORED_OWN.value, "learned": True}

    def _learn_example(self, contact_id: str, context: str, reply: str, source: ExampleSource) -> None:
        ex = ReplyExample(contact_id=contact_id, context=context, reply=reply, timestamp=self.clock(), source=source, split="TRAIN")
        self.store.add_example(ex, embed([context])[0])
        self.index.invalidate(contact_id)

    # ------------------------------------------------------------------ import / profile
    def import_chat(self, contact_id: str, display_name: str = "", export_text: str = "", from_inbox: bool = False,
                    owner_name: str = "") -> dict[str, Any]:
        if is_group_chat(contact_id):
            raise imp.ImportError_("Group chats are never used for personal reply learning.")
        if from_inbox:
            lines = imp.lines_from_inbox(self.inbox, contact_id)
            owner, contact = "you", display_name
        else:
            owners = [owner_name] if owner_name else self.owner_names
            parsed = imp.parse_export(export_text, owner_names=owners, contact_name=display_name)
            lines, owner, contact = parsed.lines, parsed.owner_name, parsed.contact_name
        self.store.upsert_contact(contact_id, display_name or contact)
        added = self.store.add_sources(contact_id, lines)
        result = self.rebuild_profile(contact_id)
        result.update({"lines_added": added, "owner_detected_as": owner,
                       "user_messages": sum(1 for ln in lines if ln.direction == Direction.USER),
                       "contact_messages": sum(1 for ln in lines if ln.direction == Direction.CONTACT)})
        return result

    def rebuild_profile(self, contact_id: str) -> dict[str, Any]:
        sources = self.store.sources(contact_id)
        name = self.store.display_name(contact_id)
        examples = imp.build_examples(contact_id, sources)
        vecs = embed([e.context for e in examples]) if examples else embed([""])[:0]
        self.store.replace_examples(contact_id, examples, vecs, sources=(ExampleSource.IMPORT.value, ExampleSource.LIVE_USER.value))
        holdout = {(e.timestamp, e.reply) for e in examples if e.split == "HOLDOUT"}
        holdout_parts = {(ts, part) for ts, rep in holdout for part in rep.split("\n")}
        user_lines = [ln for ln in sources if ln.direction == Direction.USER and (ln.timestamp, ln.text) not in holdout_parts
                      and not any(abs(ln.timestamp - ts) < 601 and ln.text in rep.split("\n") for ts, rep in holdout)]
        approved, _ = self.store.examples(contact_id, splits=("TRAIN",))
        user_lines += [ChatLine(timestamp=e.timestamp, sender="owner", direction=Direction.USER, text=e.reply)
                       for e in approved if e.source in (ExampleSource.USER_EDITED, ExampleSource.APPROVED)]
        old = self.store.load_profile(contact_id)
        prof = style_analyzer.analyze(contact_id, name, user_lines, preferences=old.preferences if old else None)
        version = self.store.save_profile(prof) if prof.messages_analyzed else 0
        self.index.invalidate(contact_id)
        self._refresh_default_profile()
        self._emit("profile", contact_id=contact_id, version=version)
        return {"contact_id": contact_id, "profile_version": version, "messages_analyzed": prof.messages_analyzed,
                "examples": len(examples), "holdout_examples": sum(1 for e in examples if e.split == "HOLDOUT"),
                "summary": prof.summary()}

    def _refresh_default_profile(self) -> None:
        lines: list[ChatLine] = []
        for c in self.store.contacts():
            if c["contact_id"] == "__default__":
                continue
            lines += [ln for ln in self.store.sources(c["contact_id"]) if ln.direction == Direction.USER]
        if lines:
            prof = style_analyzer.default_profile([], lines)
            existing = self.store.load_profile("__default__")
            if existing is None or existing.messages_analyzed != prof.messages_analyzed:
                self.store.save_profile(prof)

    def clear_profile(self, contact_id: str) -> dict[str, Any]:
        self.policy.stop_contact(contact_id)
        self.store.clear_profile(contact_id)
        self.index.invalidate(contact_id)
        return {"status": "CLEARED", "contact_id": contact_id}

    def feedback(self, contact_id: str, kind: str) -> dict[str, Any]:
        if kind not in FEEDBACK:
            raise ValueError(f"Unknown feedback: {kind}")
        prof = self.store.load_profile(contact_id)
        if prof is None:
            raise ValueError("Build the profile first.")
        prefs = dict(prof.preferences)
        for key, delta in FEEDBACK[kind].items():
            if key == "length_factor":
                prefs[key] = round(max(0.4, min(2.5, float(prefs.get(key, 1.0)) * delta)), 3)
            else:
                prefs[key] = round(float(prefs.get(key, 0)) + delta, 3)
        prefs.setdefault("feedback", []).append({"kind": kind, "at": self.clock()})
        prefs["feedback"] = prefs["feedback"][-30:]
        prof.preferences = prefs
        version = self.store.save_profile(prof)
        return {"status": "SAVED", "profile_version": version, "summary": prof.summary()}

    async def preview_style(self, contact_id: str, sample: str = "") -> dict[str, Any]:
        prof, has = self.profile_for(contact_id)
        if not sample:
            contact_lines = [ln.text for ln in self.store.sources(contact_id) if ln.direction == Direction.CONTACT]
            sample = contact_lines[-1] if contact_lines else "Are you free tomorrow?"
        d = await self.draft(contact_id, [sample])
        return {"contact_id": contact_id, "has_profile": has, "summary": prof.summary(), "sample_incoming": sample,
                "example_reply": d["candidate"].text if d["candidate"] else None,
                "target_language": d["context"].target_language}

    async def test_reply(self, contact_id: str, incoming: str) -> dict[str, Any]:
        """Generate a reply WITHOUT sending (profile quality check)."""
        d = await self.draft(contact_id, [incoming])
        cand, q = d["candidate"], d["quality"]
        return {"contact_id": contact_id, "incoming": incoming, "reply": cand.text if cand else None,
                "target_language": d["context"].target_language, "understanding": d["understanding"].__dict__,
                "quality": q.to_dict() if q else None, "would_auto_send": bool(q and q.passed and not d["understanding"].requests_pc_action),
                "examples_used": [{"them": e.example.context, "you": e.example.reply} for e in d["examples"]],
                "sent": False}

    # ------------------------------------------------------------------ grants / modes
    def enable(self, contact_ids: list[str], expires_at: float, everyone: bool = False, names: Optional[list[str]] = None) -> dict[str, Any]:
        now = self.clock()
        if everyone:
            g = self.policy.grant(GrantScope.ALL_DIRECT_CONTACTS, [], expires_at, now=now)
            msg = (f"Auto replies to all direct contacts are on for the next {_duration_words(expires_at - now)} "
                   f"(until {_fmt_until(expires_at)}). Group chats remain disabled.")
        else:
            scope = GrantScope.CONTACT if len(contact_ids) == 1 else GrantScope.CONTACTS
            g = self.policy.grant(scope, contact_ids, expires_at, now=now)
            who = ", ".join(names or [self.store.display_name(c) for c in contact_ids])
            msg = (f"Auto replies to {who} are enabled for {_duration_words(expires_at - now)} "
                   f"(until {_fmt_until(expires_at)}). Group chats remain disabled.")
            for c in contact_ids:
                self.store.upsert_contact(c)
            self._last_contact = contact_ids[-1]
        self._emit("grant", contact_id=",".join(contact_ids) or "ALL_DIRECT", grant_id=g.grant_id, expires_at=g.expires_at)
        untrained = [] if everyone else [c for c in contact_ids if self.store.load_profile(c) is None]
        if untrained:
            msg += " I haven't learned your style with them yet, so I'll use your general style."
        return {"status": "ENABLED", "grant_id": g.grant_id, "expires_at": g.expires_at, "message": msg}

    def stop(self, contact_id: str) -> dict[str, Any]:
        n = self.policy.stop_contact(contact_id)
        for bid in [k for k in self._buffers if k == contact_id]:
            self._buffers.pop(bid, None)
            t = self._flush_tasks.pop(bid, None)
            if t:
                t.cancel()
        self._emit("grant", contact_id=contact_id, stopped=True)
        return {"status": "STOPPED", "changed": n,
                "message": f"Stopped auto-replying to {self.store.display_name(contact_id)}."}

    def stop_all(self) -> dict[str, Any]:
        n = self.policy.stop_all()
        for t in self._flush_tasks.values():
            t.cancel()
        self._flush_tasks.clear()
        self._buffers.clear()
        self._emit("grant", contact_id="ALL", stopped=True)
        return {"status": "STOPPED", "revoked": n, "message": "WhatsApp auto-reply is off for everyone."}

    def set_mode(self, contact_id: str, mode: ReplyMode) -> dict[str, Any]:
        if is_group_chat(contact_id):
            raise ValueError("Group chats can't have a reply mode.")
        mode = ReplyMode(mode)
        if mode == ReplyMode.AUTO_REPLY_UNTIL:
            raise ValueError("Auto-reply needs an end time: use enable(...) with a duration.")
        if mode == ReplyMode.OFF:
            self.policy.stop_contact(contact_id)
        self.store.set_mode(contact_id, mode)
        return {"status": "OK", "mode": mode.value}

    @property
    def last_contact(self) -> str:
        return self._last_contact

    # ------------------------------------------------------------------ overview / history (UI)
    def contacts_overview(self) -> list[dict[str, Any]]:
        now = self.clock()
        grants = self.policy.active_grants(now)
        out = []
        for c in self.store.contacts():
            cid = c["contact_id"]
            if cid == "__default__" or is_group_chat(cid):
                continue
            prof = self.store.load_profile(cid)
            covering = [g for g in grants if g.covers(cid)]
            last = self.store.replies(cid, limit=1)
            counts = self.store.source_count(cid)
            out.append({
                "contact_id": cid, "display_name": c["display_name"] or cid.split("@")[0],
                "profile_status": "READY" if prof else "NO PROFILE",
                "samples": counts.get("USER", 0), "contact_samples": counts.get("CONTACT", 0),
                "language_style": prof.summary()["language"] if prof else "-",
                "tone": prof.summary()["tone"] if prof else "-",
                "confidence": round(prof.confidence, 2) if prof else 0.0,
                "profile_version": prof.profile_version if prof else 0,
                "reply_mode": ReplyMode.AUTO_REPLY_UNTIL.value if covering else c["mode"],
                "auto_reply": "ON" if covering else "OFF",
                "auto_reply_expiry": max(g.expires_at for g in covering) if covering else None,
                "last_incoming": last[0]["incoming"][:120] if last else "",
                "last_reply": last[0]["text"][:120] if last else "",
                "last_status": last[0]["status"] if last else "",
                "groups": "BLOCKED",
            })
        return out

    def history(self, contact_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [{k: r[k] for k in ("id", "incoming", "text", "status", "mode", "reason", "created_at", "send_verified", "quality")}
                for r in self.store.replies(contact_id, limit=limit)]

    def status_text(self) -> str:
        grants = self.policy.status(self.clock())
        if not grants:
            return "WhatsApp auto-reply is off."
        parts = []
        for g in grants:
            who = "all direct contacts" if g["scope"] == "ALL_DIRECT_CONTACTS" else ", ".join(self.store.display_name(c) for c in g["contact_ids"])
            parts.append(f"{who} for {g['minutes_left']} more minutes")
        return "Auto-replying to " + "; ".join(parts) + ". Groups are always blocked."

    # ------------------------------------------------------------------ restart recovery + background tasks
    def recover(self) -> dict[str, Any]:
        """On restart: expire old grants, never resend STARTED/SENDING replies (they become UNCERTAIN)."""
        expired = self.policy.expire_due(self.clock())
        stuck = self.store.replies(statuses=("SENDING", "DRAFTING"), limit=500)
        uncertain = 0
        for r in stuck:
            if r["status"] == "SENDING":
                self.store.update_reply(r["id"], status=Outcome.UNCERTAIN.value, reason="JARVIS restarted during send - not resent")
                uncertain += 1
            else:
                self.store.update_reply(r["id"], status=Outcome.NEEDS_USER_REVIEW.value, reason="interrupted by restart")
        if self.ledger is not None:
            try:
                from jarvis.security.ledger.models import LedgerState
                from jarvis.tools.base import RiskLevel
                for e in self.ledger.get_unresolved_actions():
                    if e.graph_id == "whatsapp_personal_reply" and e.status == LedgerState.STARTED:
                        self.ledger.record_outcome(e.action_id, e.fingerprint, RiskLevel.EXTERNAL_EFFECT, LedgerState.UNCERTAIN,
                                                   error_class="restart during send")
            except Exception:
                logger.debug("ledger reconciliation skipped", exc_info=True)
        return {"expired_grants": len(expired), "uncertain_replies": uncertain}

    async def tick(self) -> list[str]:
        """One background step: end expired grants now and announce it."""
        notes = []
        for g in self.policy.expire_due(self.clock()):
            who = "all direct contacts" if g.scope == GrantScope.ALL_DIRECT_CONTACTS else ", ".join(self.store.display_name(c) for c in g.contact_ids)
            note = f"Auto replies to {who} have ended."
            notes.append(note)
            self._emit("grant", contact_id=",".join(g.contact_ids) or "ALL_DIRECT", grant_id=g.grant_id, expired=True)
            await self._notify(note)
        return notes

    async def pending_decryption_retry(self) -> int:
        """Bounded, low-frequency retry when the transport can re-fetch a message by id."""
        fetch = getattr(self.transport, "get_message", None)
        if fetch is None:
            return 0
        recovered = 0
        for row in self.store.pending_decryption(max_attempts=10):
            try:
                msg = await fetch(row["message_id"], row["chat_id"])
            except Exception:
                msg = None
            self.store.mark_pending_decryption(row["message_id"], row["chat_id"])  # attempts += 1
            if msg is not None and not is_placeholder(msg):
                await self.handle_incoming(msg)
                recovered += 1
        return recovered

    def start_background(self, interval_s: float = 5.0) -> None:
        async def loop():
            n = 0
            while True:
                try:
                    await self.tick()
                    n += 1
                    if n % 12 == 0:  # about once a minute
                        await self.pending_decryption_retry()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.debug("personal reply background step failed", exc_info=True)
                await asyncio.sleep(interval_s)
        if self._background is None or self._background.done():
            self._background = asyncio.create_task(loop())

    async def close(self) -> None:
        for t in list(self._flush_tasks.values()) + ([self._background] if self._background else []):
            t.cancel()


_agent: Optional[PersonalReplyAgent] = None


def get_personal_reply_agent() -> PersonalReplyAgent:
    global _agent
    if _agent is None:
        _agent = PersonalReplyAgent()
    return _agent


def set_personal_reply_agent(agent: Optional[PersonalReplyAgent]) -> None:
    global _agent
    _agent = agent
