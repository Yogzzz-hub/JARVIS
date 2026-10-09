"""WhatsApp personal reply agent: contact-specific style + timed, policy-gated auto-reply.

Live pipeline (see docs/WHATSAPP_PERSONAL_REPLY_AGENT.md):

    incoming event -> own message? (learn, never reply) -> GROUP? (ignore, structural)
    -> placeholder / undecrypted? (PENDING_DECRYPTION, wait for the real body)
    -> claim message_id (persistent dedupe) -> AutoReplyPolicy (grant / base mode / expiry)
    -> short coalescing window -> profile + recent thread + top-K owner examples
    -> local LLM -> quality gate -> AUTO / ASK / SUGGEST -> re-check expiry & STOP
    -> ActionLedger (PREPARED -> STARTED -> VERIFIED | FAILED | UNCERTAIN) -> send -> verify

    An incoming message can only ever produce a text reply to the
same direct chat it came from.
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from jarvis.integrations.whatsapp.personal_reply import feed
from jarvis.integrations.whatsapp.personal_reply import importer as imp
from jarvis.integrations.whatsapp.personal_reply import style_analyzer
from jarvis.integrations.whatsapp.personal_reply.auto_reply_policy import AutoReplyPolicy, PolicyDecision
from jarvis.integrations.whatsapp.personal_reply.context_builder import build as build_context
from jarvis.integrations.whatsapp.personal_reply.dedupe import is_group_chat, is_placeholder
from jarvis.integrations.whatsapp.personal_reply.example_index import ContactExampleIndex, embed
from jarvis.integrations.whatsapp.personal_reply.models import (
    Authorship, ChatLine, ContactStyleProfile, Direction, ExampleSource, GrantScope, IncomingBatch, Outcome, ReplyCandidate,
    ReplyExample, ReplyMode,
)
from jarvis.integrations.whatsapp.personal_reply.quality_gate import evaluate, has_ai_phrases, sensitive_topics
from jarvis.integrations.whatsapp.personal_reply.reply_generator import ReplyGenerator
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore, text_hash
from jarvis.integrations.whatsapp.personal_reply.understand import Answerability, classify_answerability, memory_need, understand

logger = logging.getLogger("jarvis.whatsapp.personal_reply")

MIN_PROFILE_CONFIDENCE_AUTO = 0.35


def _hold_status(gate: str) -> str:
    return {"REQUIRES_TOOL": "TOOL_REQUIRED", "REQUIRES_CLARIFICATION": "CLARIFICATION_REQUIRED",
            "NOT_ANSWERABLE": "NO_REPLY_NEEDED"}.get(gate, "OWNER_INPUT_REQUIRED")
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


_AWAY_FIX = {"metting": "meeting", "meting": "meeting", "mtg": "meeting", "meetin": "meeting", "gng": "going",
             "goin": "going", "bzy": "busy", "wrk": "work", "clg": "college", "ofc": "office", "msg": "message",
             "ur": "your", "u": "you", "r": "are", "tmrw": "tomorrow", "l8r": "later"}


def away_text(note: str) -> str:
    """Tidy the owner's dictated away message without adding promises."""
    t = " ".join((note or "").split()).strip(" .,!")
    t = re.sub(r"^(?:that|saying|to say|say|tell (?:them|him|her|everyone)(?: that)?)\s+", "", t, flags=re.I)
    t = re.sub(r"(\w)\1{2,}", r"\1\1", t)
    t = " ".join(_AWAY_FIX.get(w.lower(), w) for w in t.split(" "))
    t = re.sub(r"\bi am\b", "I'm", t, flags=re.I)
    t = re.sub(r"\bi(?=['\s]|$)", "I", t)
    if not t:
        return "Got your message."
    t = t[0].upper() + t[1:]
    return t + "."


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
                 auto_reply_untrained: bool = False, notifier: Optional[Callable[[str], Any]] = None,
                 answerability_classifier: Callable[[str, list[tuple[bool, str]]], Answerability] = classify_answerability,
                 semantic_context_enabled: bool = True) -> None:
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
        self.answerability_classifier = answerability_classifier
        self.semantic_context_enabled = semantic_context_enabled
        self.notifier = notifier
        self.index = ContactExampleIndex(self.store)
        self._buffers: dict[str, IncomingBatch] = {}
        self._noted: set[tuple[str, str]] = set()  # (grant, contact) already sent the away message
        self._flush_tasks: dict[str, asyncio.Task] = {}
        self._owner_replied_at: dict[str, float] = {}
        self._last_contact: str = ""
        self._sent_parts: dict[str, list[tuple[str, str, float]]] = {}
        self._background: Optional[asyncio.Task] = None
        self._profile_update_tasks: dict[str, asyncio.Task] = {}
        self.registered_sender = None
        self._brain_jobs = None

    @property
    def brain_jobs(self):
        if self._brain_jobs is None:
            from .brain_jobs import BrainJobs
            self._brain_jobs = BrainJobs(self)
        return self._brain_jobs

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
        try:
            from jarvis.core.language_shadow import get_language_service
            if not getattr(message, 'history', False):
                get_language_service().submit(text, 'whatsapp', mode='conversation', event_id=mid)
        except Exception:
            pass  # Shadow understanding never changes truth, style, or send authorization.
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
        from jarvis.core.language_shadow import generated_auto_reply_blocked
        if decision.auto and generated_auto_reply_blocked():
            return {"status": Outcome.NEEDS_USER_REVIEW.value,
                    "reason": "Generated auto-reply is OFF during multilingual language shadow",
                    "auto_reply": False}
        if self._owner_replied_at.get(cid, 0) > batch.received_at:
            self._activity(cid, name, "Skipped", "you replied yourself")
            return {"status": Outcome.OWNER_REPLIED.value}
        intelligence = None
        version = None
        if self.semantic_context_enabled and getattr(self.inbox, "db_path", None):
            from jarvis.integrations.whatsapp.intelligence.engine import get_intelligence
            from jarvis.integrations.whatsapp.intelligence.language import semantic_frame, reply_necessity
            intelligence = get_intelligence(self.inbox)
            version = intelligence.store.version(cid)
            if decision.auto and reply_necessity(semantic_frame(cid, batch.text, batch.received_at)) == "NO_REPLY_NEEDED":
                intelligence.store.metric("no_reply_needed")
                return {"status": "NO_REPLY_NEEDED", "reason": "Acknowledgement does not need a further reply"}
        reply_id = self.store.start_reply(batch.last_message_id, batch.message_ids, cid, batch.chat_id, decision.mode.value,
                                          decision.grant.grant_id if decision.grant else None, batch.text)
        if reply_id is None:
            return {"status": Outcome.DUPLICATE.value}
        if decision.auto and decision.grant is not None and decision.grant.note:
            # the owner dictated what to say ("tell them I'm in a meeting"): said once per person, no model involved
            key = (decision.grant.grant_id, cid)
            if key in self._noted:
                self.store.update_reply(reply_id, status=Outcome.NEEDS_USER_REVIEW.value, reason="away message already sent")
                self._activity(cid, name, "Not sent", "already told them you're away")
                return {"status": Outcome.NEEDS_USER_REVIEW.value, "reply_id": reply_id, "reason": "away message already sent"}
            self._noted.add(key)
            text = away_text(decision.grant.note)
            self.store.update_reply(reply_id, text=text, draft_hash=text_hash(text))
            self._activity(cid, name, "Away message")
            return await self._send(reply_id, cid, batch.chat_id, name, text, decision, batch.last_message_id)
        self._activity(cid, name, "Analyzing")
        draft = await self.draft(cid, batch.texts, exclude_message_ids=set(batch.message_ids), name=name)
        if decision.auto and not self.policy.still_allowed(decision, stop_gen, now=self.clock()):
            self.store.update_reply(reply_id, status=Outcome.EXPIRED.value, reason="auto-reply stopped while drafting")
            return {"status": Outcome.EXPIRED.value, "reply_id": reply_id}
        cand, quality, profile, ctx, und = draft["candidate"], draft["quality"], draft["profile"], draft["context"], draft["understanding"]
        self._activity(cid, name, "Style", f"{ctx.target_language.title()}/{profile.effective_formality().replace('_', ' ').title()}")
        if cand is None:
            hold_reason = draft.get("hold_reason", "reply model unavailable")
            self.store.update_reply(reply_id, status=Outcome.NEEDS_USER_REVIEW.value, reason=hold_reason)
            self._activity(cid, name, "NOT SENT", "needs owner context" if draft.get("hold_reason") else "needs review (model unavailable)")
            await self._notify(f"New WhatsApp message from {name} needs your reply.")
            return {"status": Outcome.NEEDS_USER_REVIEW.value, "reply_id": reply_id, "reason": hold_reason,
                    "answerability": draft["answerability"].category,
                    "required_state": draft["answerability"].gate}
        self.store.update_reply(reply_id, text=cand.text, draft_hash=text_hash(cand.text), quality=quality.to_dict())
        self._activity(cid, name, "Draft generated", "instant (your own usual reply)" if cand.generator == "instant" else "")
        reasons = list(quality.reasons)
        if und.requests_pc_action:
            reasons.append("asks for files or actions - conversation reply only")
        if und.confidence < 0.5 or und.intent in ("EMPTY", "UNCLEAR"):
            reasons.append("could not understand the message")
        if draft["modality"].modality == "STICKER_ONLY":
            reasons.append("sticker reply needs owner review and a separately verified media send")
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
        if intelligence is not None and version != intelligence.store.version(cid):
            self.store.update_reply(reply_id, status=Outcome.NEEDS_USER_REVIEW.value, reason="conversation changed while drafting")
            return {"status": Outcome.NEEDS_USER_REVIEW.value, "reply_id": reply_id, "reason": "stale conversation"}
        return await self._send(reply_id, cid, batch.chat_id, name, cand.text, decision, batch.last_message_id)

    async def draft(self, contact_id: str, texts: list[str], exclude_message_ids: set[str] | None = None,
                    name: str = "") -> dict[str, Any]:
        """Everything short of sending: used by the live pipeline, Test Reply and Preview Style."""
        t0 = time.perf_counter()
        profile, has_profile = self.profile_for(contact_id)
        t_profile = time.perf_counter()
        current = "\n".join(t for t in texts if t)
        und = understand(current, use_jde=self.use_jde)
        t_understand = time.perf_counter()
        thread = self._thread(contact_id, exclude_message_ids or set())
        t_thread = time.perf_counter()
        answerability = self.answerability_classifier(current, thread)
        retrieval_need = memory_need(current, answerability.category)
        t_classified = time.perf_counter()
        examples = (self.index.retrieve(contact_id, current, k=6)
                    if has_profile and answerability.gate == "ANSWERABLE"
                    and retrieval_need != "MEMORY_NOT_NEEDED" else [])
        t_retrieved = time.perf_counter()
        from jarvis.integrations.whatsapp.personal_reply.modality import predict
        from jarvis.integrations.whatsapp.personal_reply.sticker_memory import StickerMemory
        sticker_candidates = StickerMemory(self.store).candidates(contact_id, current, und.conversation_mode)
        modality = predict(profile, und.conversation_mode, sensitive=bool(sensitive_topics(current)),
                           sticker_candidates=sticker_candidates)
        ctx = build_context(contact_id, name or self.store.display_name(contact_id), profile, thread, examples, texts,
                            reply_policy_extra=f"Preferred owner reply modality: {modality.modality}.")
        from jarvis.integrations.whatsapp.personal_reply.conversation_grounding import missing_owner_status, owner_clarification
        if missing_owner_status(current, thread):
            clarification = owner_clarification(self.store.sources(contact_id), self.clock())
            if clarification:
                cand = ReplyCandidate(text=clarification, understood=False, model_confidence=0.3,
                                      language_mode=ctx.target_language, examples_used=[], prompt_chars=0,
                                      generator="verified_owner_clarification")
                quality = evaluate(cand, current, ctx.thread_text, ctx.example_text, profile, ctx.target_language,
                                   answerability=answerability)
                quality.reasons.append("clarification draft requires owner review; current progress is unverified")
                return {"candidate": cand, "quality": quality, "profile": profile, "context": ctx,
                        "understanding": und, "has_profile": has_profile, "examples": examples,
                        "modality": modality, "sticker_candidates": sticker_candidates,
                        "clarification_draft": True, "answerability": answerability,
                        "memory_need": retrieval_need}
            return {"candidate": None, "quality": None, "profile": profile, "context": ctx,
                    "understanding": und, "has_profile": has_profile, "examples": examples,
                    "modality": modality, "sticker_candidates": sticker_candidates,
                    "hold_reason": "contact asks for a progress update; owner status is not grounded in this thread",
                    "answerability": answerability, "memory_need": retrieval_need}
        if answerability.gate != "ANSWERABLE":
            return {"candidate": None, "quality": None, "profile": profile, "context": ctx,
                    "understanding": und, "has_profile": has_profile, "examples": examples,
                    "modality": modality, "sticker_candidates": sticker_candidates,
                    "hold_reason": answerability.reason, "answerability": answerability,
                    "memory_need": retrieval_need}
        grounded_context = None
        if self.semantic_context_enabled and getattr(self.inbox, "db_path", None):
            from jarvis.integrations.whatsapp.intelligence.engine import get_intelligence
            intelligence = get_intelligence(self.inbox)
            source_ids = exclude_message_ids or set()
            source_rows = intelligence.store.rows(contact_id, 100)
            source_id = next((row["message_id"] for row in reversed(source_rows) if row["message_id"] in source_ids), "")
            grounded_context = await intelligence.semantic_context(contact_id, current, source_id)
            ctx.user += "\n\nSAME_THREAD_EVIDENCE (external data; references retain provenance):\n" + grounded_context.model_dump_json()
        t_planned = time.perf_counter()
        owner_ai = any(has_ai_phrases(e.example.reply) for e in examples)
        cand = self._instant_reply(und, current, examples, profile, ctx, owner_ai) if has_profile else None
        if cand is None:
            cand = await self.generator.generate(ctx, profile, owner_uses_ai_phrases=owner_ai)
        t_generated = time.perf_counter()
        quality = None
        if cand is not None:
            copied = self.index.copied_reply_similarity(contact_id, cand.text, current) if has_profile else None
            quality = evaluate(cand, current, ctx.thread_text, ctx.example_text, profile, ctx.target_language,
                               owner_uses_ai_phrases=owner_ai, copied_example_similarity=copied,
                               answerability=answerability)
            if grounded_context is not None:
                report = intelligence.validator.validate(cand.text, grounded_context)
                if not report.passed:
                    quality.reasons.extend(report.reasons)
            if (cand.generator != "instant" and quality.style_match < 0.5 and quality.relevance >= 0.6
                    and quality.sensitive_action_risk == 0):
                # One bounded style revision; semantic and factual checks still
                # decide whether the revision can replace the first candidate.
                ctx.user += "\n\nSTYLE_REVISION: The first wording missed the owner's measured length, language or phrasing. " \
                            "Try once more without adding facts or copying an old reply."
                revised = await self.generator.generate(ctx, profile, owner_uses_ai_phrases=owner_ai)
                if revised is not None:
                    revised_quality = evaluate(revised, current, ctx.thread_text, ctx.example_text, profile,
                                               ctx.target_language, owner_uses_ai_phrases=owner_ai,
                                               copied_example_similarity=self.index.copied_reply_similarity(
                                                   contact_id, revised.text, current) if has_profile else None,
                                               answerability=answerability)
                    if grounded_context is not None:
                        revised_report = intelligence.validator.validate(revised.text, grounded_context)
                        if not revised_report.passed:
                            revised_quality.reasons.extend(revised_report.reasons)
                    if (revised_quality.style_match > quality.style_match
                            and revised_quality.relevance >= quality.relevance
                            and revised_quality.hallucination_risk <= quality.hallucination_risk
                            and revised_quality.sensitive_action_risk <= quality.sensitive_action_risk):
                        cand, quality = revised, revised_quality
        return {"candidate": cand, "quality": quality, "profile": profile, "context": ctx, "understanding": und,
                "has_profile": has_profile, "examples": examples, "modality": modality,
                "sticker_candidates": sticker_candidates, "answerability": answerability,
                "memory_need": retrieval_need,
                "timing_ms": {"profile_lookup": round((t_profile-t0)*1000, 2),
                              "classification": round(((t_understand-t_profile)+(t_classified-t_thread))*1000, 2),
                              "recent_context": round((t_thread-t_understand)*1000, 2),
                              "retrieval": round((t_retrieved-t_classified)*1000, 2),
                              "planning": round((t_planned-t_retrieved)*1000, 2),
                              "generation": round((t_generated-t_planned)*1000, 2),
                              "validation_and_revision": round((time.perf_counter()-t_generated)*1000, 2),
                              "total": round((time.perf_counter()-t0)*1000, 2)}}

    INSTANT_SIMILARITY = 0.88

    def _instant_reply(self, und, current: str, examples: list, profile, ctx, owner_ai: bool):
        """Greetings and acknowledgements the owner has answered before ("gm" -> "gm da ☀️"): the owner's own reply,
        in milliseconds, without the language model. Anything longer or new still goes to the model."""
        if und.intent not in ("GREETING", "ACK") or len(current.split()) > 5 or "\n" in current.strip():
            return None
        good = [e for e in examples if e.similarity >= self.INSTANT_SIMILARITY and len(e.example.context.split()) <= 6
                and "\n" not in e.example.context.strip() and 0 < len(e.example.reply.split()) <= 8]
        if not good:
            return None
        best = max(good, key=lambda e: e.score)
        from jarvis.integrations.whatsapp.personal_reply.models import ReplyCandidate
        from jarvis.integrations.whatsapp.personal_reply.reply_generator import postprocess
        return ReplyCandidate(text=postprocess(best.example.reply, profile, owner_ai), understood=True, model_confidence=0.9,
                              language_mode=ctx.target_language, examples_used=[best.example.example_id], prompt_chars=0,
                              generator="instant")

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
        parts = self._message_parts(contact_id, text)
        for part in parts:
            self._remember_sent_part(chat_id, part)
        try:
            ack = await asyncio.wait_for(self._send_registered(chat_id, parts[0]), timeout=30.0)
        except ConnectionError as exc:  # transport refused before anything left the PC
            return self._finish(reply_id, action_id, fingerprint, Outcome.FAILED, f"not connected: {exc}", contact_id, name)
        except Exception as exc:  # timeout / unknown: the message MAY have been sent - never resend blindly
            return self._finish(reply_id, action_id, fingerprint, Outcome.UNCERTAIN, f"{type(exc).__name__}: {exc}", contact_id, name)
        ack = ack or {}
        for i, part in enumerate(parts[1:], 2):  # the owner texts this person in short bursts: same here
            if ack.get("success") is False or ack.get("error"):
                break
            await asyncio.sleep(self.burst_gap_s)
            try:
                more = await asyncio.wait_for(self._send_registered(chat_id, part), timeout=30.0) or {}
                self._remember_sent_part(chat_id, "", str(more.get("message_id") or (more.get("result") or {}).get("message_id") or ""))
            except Exception as exc:
                return self._finish(reply_id, action_id, fingerprint, Outcome.UNCERTAIN,
                                    f"sent part {i - 1} of {len(parts)}, then {type(exc).__name__}: {exc}", contact_id, name)
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

    burst_gap_s = 0.8

    async def _send_registered(self, chat_id, text):
        if self.registered_sender is not None:
            result = await self.registered_sender(chat_id, text)
            return {"success": result.get("status") == "SENT", "result": result,
                    "error": None if result.get("status") == "SENT" else result.get("message", "send failed"),
                    "status": result.get("status")}
        return await self.transport.send_text(to=chat_id, text=text)

    def _message_parts(self, contact_id: str, text: str) -> list[str]:
        """One message, or 2-3 short ones when that is how the owner texts this person."""
        lines = [ln.strip() for ln in (text or "").split("\n") if ln.strip()]
        if len(lines) < 2:
            return [text.strip()]
        try:
            burst = self.profile_for(contact_id)[0].burst_rate
        except Exception:
            burst = 0.0
        if burst < 0.3 or len(lines) > 3:
            return [text.strip()]
        return lines

    def _remember_sent_part(self, chat_id: str, text: str = "", message_id: str = "") -> None:
        now = self.clock()
        bucket = self._sent_parts.setdefault(chat_id, [])
        bucket[:] = [(h, m, t) for h, m, t in bucket if now - t < 600][-20:]
        bucket.append((text_hash(text.strip()) if text else "", message_id, now))

    def _is_own_part(self, chat_id: str, message_id: str, text: str) -> bool:
        h = text_hash(text.strip()) if text else ""
        return any((h and h == ph) or (message_id and message_id == pm) for ph, pm, _ in self._sent_parts.get(chat_id, []))

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
        was_edited = bool(edited_text and edited_text.strip() != (row["text"] or "").strip())
        name = self.store.display_name(row["contact_id"])
        result = await self._send(reply_id, row["contact_id"], row["chat_id"], name, text, None, row["incoming_message_id"])
        # The candidate stays separate. Neither an unsent edit nor an echoed
        # JARVIS send is ever relabelled as organically typed owner text.
        if result.get("status") == Outcome.VERIFIED.value and result.get("sent_message_id"):
            final_id = result["sent_message_id"]
            edit_ratio = 1.0 - difflib.SequenceMatcher(None, row["text"] or "", text).ratio()
            if was_edited:
                self.store.record_edit(reply_id, row["contact_id"], row["text"] or "", text, final_id, edit_ratio)
            provenance = Authorship.USER_EDITED_AI_DRAFT if was_edited else Authorship.USER_APPROVED_AI_DRAFT
            delta = {}
            if was_edited:
                from jarvis.integrations.whatsapp.personal_reply import language as lang
                before_words = max(1, len((row['text'] or '').split()))
                delta = {'length_ratio': round(len(text.split()) / before_words, 3),
                         'emoji_before': bool(lang.emojis(row['text'] or '')),
                         'emoji_after': bool(lang.emojis(text)),
                         'language_before': lang.detect(row['text'] or '').label,
                         'language_after': lang.detect(text).label}
            self.store.record_draft_feedback(reply_id, row['contact_id'], 'EDITED_SENT' if was_edited else 'APPROVED_SENT',
                                             row['text'] or '', text, edit_ratio, final_id, delta)
            if was_edited:
                profile = self.store.load_profile(row['contact_id'])
                if profile is not None:
                    prefs = dict(profile.preferences)
                    prior = float(prefs.get('length_factor', 1.0))
                    prefs['length_factor'] = round(max(.5, min(2.0, prior * (.9 + .1 * delta['length_ratio']))), 3)
                    prefs['reviewed_edits'] = int(prefs.get('reviewed_edits', 0)) + 1
                    profile.preferences = prefs
                    self.store.save_profile(profile)
            self.store.add_sources(row["contact_id"], [ChatLine(timestamp=self.clock(), sender="owner",
                                   direction=Direction.USER, text=text, message_id=final_id,
                                   provenance=provenance, provenance_confidence=1.0,
                                   reply_to=row['incoming_message_id'])], import_id="reviewed_draft")
            if row['incoming']:
                from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import evidence_weight
                example = ReplyExample(contact_id=row['contact_id'], context=row['incoming'], reply=text,
                                       timestamp=self.clock(), source=ExampleSource.USER_EDITED, split='TRAIN',
                                       provenance=provenance, evidence_weight=evidence_weight(provenance, 1.0))
                self.store.add_example(example, embed([row['incoming']])[0])
                self.index.invalidate(row['contact_id'])
            self._schedule_profile_update(row['contact_id'])
        elif result.get('status') == Outcome.UNCERTAIN.value:
            self.store.record_draft_feedback(reply_id, row['contact_id'], 'SEND_UNCERTAIN', row['text'] or '', text)
        return result

    def reject_reply(self, reply_id: int) -> dict[str, Any]:
        self.store.update_reply(reply_id, status="REJECTED")
        row = self.store.reply(reply_id)
        if row:
            self.store.record_draft_feedback(reply_id, row['contact_id'], 'NO_REPLY', row['text'] or '')
        return {"status": "REJECTED"}

    # ------------------------------------------------------------------ learning (owner-authored text only)
    def learn_owner_message(self, message: Any) -> dict[str, Any]:
        chat_id = getattr(message, "chat_id", "") or ""
        text = (getattr(message, "text", "") or "").strip()
        mid = getattr(message, "message_id", "") or ""
        if is_group_chat(chat_id) or not text or is_placeholder(message) or getattr(message, "type", "text") != "text":
            return {"status": Outcome.IGNORED_OWN.value}
        generated = False
        if getattr(self.inbox, "db_path", None):
            from jarvis.integrations.whatsapp.intelligence.engine import get_intelligence
            generated = get_intelligence(self.inbox).store.is_generated(chat_id, mid, text)
        if generated or self._is_own_part(chat_id, mid, text) or self.store.is_sent_reply(chat_id, sent_message_id=mid, text=text):
            # JARVIS's own reply echoed back from the phone: not the owner replying, never style training data
            return {"status": Outcome.IGNORED_OWN.value, "reason": "JARVIS's own reply is never style training data"}
        self._owner_replied_at[chat_id] = self.clock()
        pending = self._flush_tasks.pop(chat_id, None)
        if pending and not pending.done():
            pending.cancel()
            self._buffers.pop(chat_id, None)
        # A fromMe echo can originate on any linked device, including JARVIS.
        # Absence from a completed-send log is insufficient while an external
        # send may still be in flight. Require a separate exact-ID owner proof.
        proof = getattr(message, 'owner_origin_proof', '')
        from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import LegacyProvenanceResolver
        resolver = LegacyProvenanceResolver(self.inbox.db_path, self.store.path)
        attribution = resolver.classify_live(message_id=mid, chat_id=chat_id, timestamp=self.clock(),
                                             message_type=getattr(message, 'type', 'text'), text=text,
                                             source_device_proof=proof)
        if attribution.provenance != Authorship.VERIFIED_MANUAL_OWNER_SEND:
            return {"status": Outcome.IGNORED_OWN.value, "reason": "manual authorship unproven"}
        self.store.add_sources(chat_id, [ChatLine(timestamp=self.clock(), sender="owner", direction=Direction.USER,
                                                  text=text, message_id=mid,
                                                  provenance=Authorship.VERIFIED_MANUAL_OWNER_SEND,
                                                  provenance_confidence=1.0,
                                                  provenance_reasons=list(attribution.reasons))], import_id="live")
        context = [t for mine, t in self._thread(chat_id, {mid}, limit=6) if not mine][-3:]
        if context:
            self._learn_example(chat_id, "\n".join(context), text, ExampleSource.LIVE_USER)
        self._schedule_profile_update(chat_id)
        return {"status": Outcome.IGNORED_OWN.value, "learned": True}

    def _learn_example(self, contact_id: str, context: str, reply: str, source: ExampleSource) -> None:
        provenance = (Authorship.USER_EDITED_AI_DRAFT if source == ExampleSource.USER_EDITED else
                      Authorship.VERIFIED_MANUAL_OWNER_SEND if source == ExampleSource.LIVE_USER else Authorship.USER_TYPED)
        ex = ReplyExample(contact_id=contact_id, context=context, reply=reply, timestamp=self.clock(), source=source,
                          split="TRAIN", provenance=provenance, evidence_weight=0.9 if source == ExampleSource.USER_EDITED else 1.0)
        self.store.add_example(ex, embed([context])[0])
        self.index.invalidate(contact_id)

    def _schedule_profile_update(self, contact_id: str) -> None:
        task = self._profile_update_tasks.get(contact_id)
        if task is not None and not task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.rebuild_profile(contact_id)
            return
        async def refresh() -> None:
            await asyncio.sleep(2)
            if self._brain_jobs is not None:
                await asyncio.to_thread(self._brain_jobs.start, 'CONTACT', contact_id)
            else:
                await asyncio.to_thread(self.rebuild_profile, contact_id)
        self._profile_update_tasks[contact_id] = loop.create_task(refresh())

    # ------------------------------------------------------------------ import / profile
    def import_chat(self, contact_id: str, display_name: str = "", export_text: str = "", from_inbox: bool = False,
                    owner_name: str = "", verified_fixture: bool = False) -> dict[str, Any]:
        if is_group_chat(contact_id):
            raise imp.ImportError_("Group chats are never used for personal reply learning.")
        if from_inbox:
            from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import LegacyProvenanceResolver
            resolver = LegacyProvenanceResolver(self.inbox.db_path, self.store.path)
            lines = imp.lines_from_inbox(self.inbox, contact_id, resolver=resolver)
            owner, contact = "you", display_name
        else:
            owners = [owner_name] if owner_name else self.owner_names
            chats = feed.parse_any(export_text, owner_names=owners, contact_name=display_name)
            if len(chats) != 1:
                raise imp.ImportError_(f"That file has {len(chats)} chats; import it with 'learn my WhatsApp chats' "
                                       "(the feed folder) so each chat goes to the right person.")
            parsed = chats[0].chat
            lines, owner, contact = parsed.lines, parsed.owner_name, parsed.contact_name
            if verified_fixture:
                # Test harnesses with synthetic, known-authored rows may state
                # provenance explicitly. Public REST imports never expose this.
                from dataclasses import replace
                lines = [replace(line, provenance=Authorship.USER_TYPED,
                                 provenance_confidence=1.0, provenance_reasons=['verified_test_fixture'])
                         if line.direction == Direction.USER else line for line in lines]
        return self._import_lines(contact_id, display_name or contact, lines, owner,
                                  import_id='legacy_inbox' if from_inbox else '')

    def _import_lines(self, contact_id: str, display_name: str, lines: list, owner: str,
                      import_id: str = '') -> dict[str, Any]:
        if is_group_chat(contact_id):
            raise imp.ImportError_("Group chats are never used for personal reply learning.")
        self.store.upsert_contact(contact_id, display_name)
        added = self.store.add_sources(contact_id, lines, import_id=import_id)
        if import_id == 'legacy_inbox':
            self.store.record_legacy_audit([(ln.message_id, contact_id, ln.provenance.value,
                                            ln.provenance_confidence, ln.provenance_reasons)
                                            for ln in lines if ln.direction == Direction.USER])
        result = self.rebuild_profile(contact_id)
        result.update({"lines_added": added, "owner_detected_as": owner,
                       "user_messages": sum(1 for ln in lines if ln.direction == Direction.USER),
                       "contact_messages": sum(1 for ln in lines if ln.direction == Direction.CONTACT)})
        return result

    def import_file(self, data: bytes | str, filename: str = "", contact_id: str = "", display_name: str = "",
                    owner_name: str = "") -> list[dict[str, Any]]:
        """Import a chat file in any supported format (see ``feed``). Each one-to-one chat in it is saved for its
        person: the JID in the file, the contact given, or the saved contact with that name (never a guess)."""
        owners = [owner_name] if owner_name else self.owner_names
        results = []
        for fc in feed.parse_any(data, filename, owner_names=owners, contact_name=display_name):
            cid = contact_id if contact_id and len(results) == 0 else self._contact_for(fc.contact_hint or fc.chat.contact_name)
            name = display_name or fc.chat.contact_name or fc.contact_hint
            if not cid:
                results.append({"status": "NEEDS_CONTACT", "name": name, "format": fc.source_format,
                                "message": f"Which WhatsApp contact is '{name}'? Import it from their Contacts page."})
                continue
            res = self._import_lines(cid, name, fc.chat.lines, fc.chat.owner_name)
            res.update({"status": "IMPORTED", "format": fc.source_format, "name": name})
            results.append(res)
        return results

    def _contact_for(self, hint: str) -> str:
        hint = (hint or "").strip()
        if not hint:
            return ""
        if "@" in hint:
            return "" if is_group_chat(hint) else hint
        digits = re.sub(r"\D", "", hint)
        if len(digits) >= 10 and len(digits) >= len(hint.replace(" ", "").replace("+", "")) - 1:
            return f"{digits}@s.whatsapp.net"
        known = [c for c in self.store.contacts() if (c.get("display_name") or "").strip().lower() == hint.lower()]
        if len(known) == 1:
            return known[0]["contact_id"]
        try:
            from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
            contact, ambiguous, _ = ContactResolver().resolve(hint)
            if contact is not None and not ambiguous:
                return contact.jid if "@" in contact.jid else f"{re.sub(r'[^0-9]', '', contact.jid)}@s.whatsapp.net"
        except Exception:
            pass
        return ""

    def import_feed_folder(self, folder: Optional[Path] = None) -> dict[str, Any]:
        """Import every new chat file dropped into ``data/whatsapp_feed`` (each file once, by content)."""
        folder = Path(folder or feed.FEED_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        ledger_path = folder / ".imported.json"
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            ledger = {}
        imported, pending, failed = [], [], []
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in (".txt", ".zip", ".json", ".csv"):
                continue
            data = path.read_bytes()
            digest = feed.file_hash(data)
            if ledger.get(digest):
                continue
            hint = path.parent.name if path.parent != folder else ""
            try:
                results = self.import_file(data, path.name, display_name=hint)
            except imp.ImportError_ as exc:
                failed.append({"file": path.name, "reason": str(exc)})
                continue
            done = [r for r in results if r["status"] == "IMPORTED"]
            imported += [{"file": path.name, **r} for r in done]
            pending += [{"file": path.name, **r} for r in results if r["status"] != "IMPORTED"]
            if done and len(done) == len(results):
                ledger[digest] = path.name
        try:
            ledger_path.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
        except Exception:
            pass
        people = ", ".join(f"{r['name']} ({r['messages_analyzed']} of your messages)" for r in imported)
        msg = f"Learned your style with {people}." if imported else "No new chat files in the feed folder."
        if pending:
            msg += " Couldn't tell who these are: " + ", ".join(p["name"] or p["file"] for p in pending) + \
                   " - put each file in a folder named after the contact."
        if failed:
            msg += f" {len(failed)} file(s) couldn't be read."
        return {"imported": imported, "pending": pending, "failed": failed, "folder": str(folder), "message": msg}

    def rebuild_profile(self, contact_id: str) -> dict[str, Any]:
        sources = self.store.sources(contact_id)
        name = self.store.display_name(contact_id)
        with self.store._lock, self.store._conn() as conn:
            conn.execute("UPDATE wa_pr_evaluations SET approved_at=NULL WHERE contact_id=?", (contact_id,))
        examples = imp.build_examples(contact_id, sources)
        vecs = embed([e.context for e in examples]) if examples else embed([""])[:0]
        self.store.replace_examples(contact_id, examples, vecs, sources=(ExampleSource.IMPORT.value, ExampleSource.LIVE_USER.value,
                                                                         ExampleSource.USER_EDITED.value))
        train_cutoff = max((e.timestamp for e in examples if e.split == "TRAIN"), default=float("inf"))
        evaluation_replies = {(e.timestamp, e.reply) for e in examples if e.split != "TRAIN"}
        holdout_parts = {(ts, part) for ts, rep in evaluation_replies for part in rep.split("\n")}
        user_lines = [ln for ln in sources if ln.direction == Direction.USER
                      and ln.provenance in (Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND,
                                            Authorship.USER_EDITED_AI_DRAFT, Authorship.USER_APPROVED_AI_DRAFT,
                                            Authorship.VERIFIED_LEGACY_OWNER, Authorship.LEGACY_OWNER_LIKELY)
                      and ln.timestamp <= train_cutoff
                      and (ln.timestamp, ln.text) not in holdout_parts
                      and not any(abs(ln.timestamp - ts) < 601 and ln.text in rep.split("\n")
                                  for ts, rep in evaluation_replies)]
        old = self.store.load_profile(contact_id)
        prof = style_analyzer.analyze(contact_id, name, user_lines, preferences=old.preferences if old else None)
        from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import evidence_weight
        with self.store._conn() as conn:
            sticker_rows = conn.execute("SELECT provenance,provenance_confidence FROM wa_pr_sticker_usage WHERE contact_id=?",
                                        (contact_id,)).fetchall()
        sticker_weight = sum(evidence_weight(Authorship(r[0]), r[1]) for r in sticker_rows)
        if sticker_weight:
            prof.modality_counts["STICKER_ONLY"] = round(sticker_weight, 3)
            prof.sticker_frequency = round(sticker_weight / max(1, prof.effective_evidence + sticker_weight), 3)
        if prof.messages_analyzed:
            version = self.store.save_profile(prof)
        else:
            self.store.clear_profile(contact_id, keep_sources=True)
            version = 0
        self.index.invalidate(contact_id)
        self._refresh_default_profile()
        self._emit("profile", contact_id=contact_id, version=version)
        return {"contact_id": contact_id, "profile_version": version, "messages_analyzed": prof.messages_analyzed,
                "examples": len(examples), "holdout_examples": sum(1 for e in examples if e.split == "HOLDOUT"),
                "summary": prof.summary()}

    def refresh_all(self) -> dict[str, Any]:
        results = [self.rebuild_profile(row["contact_id"]) for row in self.store.contacts()
                   if row["contact_id"] != "__default__" and not is_group_chat(row["contact_id"])]
        return {"contacts": len(results), "valid_reply_pairs": sum(r["examples"] for r in results),
                "owner_authored_messages": sum(r["messages_analyzed"] for r in results),
                "results": results}

    def explain_style(self, contact_id: str) -> dict[str, Any]:
        profile = self.store.load_profile(contact_id)
        with self.store._conn() as conn:
            rows = conn.execute("SELECT provenance,count(*) FROM wa_pr_sources WHERE contact_id=? AND direction='USER' "
                                "GROUP BY provenance", (contact_id,)).fetchall()
        provenance = {row[0]: row[1] for row in rows}
        return {"contact_id": contact_id, "ready": bool(profile and profile.messages_analyzed),
                "summary": profile.summary() if profile else None, "owner_source_counts": provenance,
                "explanation": "Verified and lower-weight legacy owner evidence shape drafts. Generated, "
                               "draft-only and unattributed outgoing messages are excluded; legacy alone never permits auto-reply."}

    def maturity(self, contact_id: str) -> str:
        profile = self.store.load_profile(contact_id)
        if profile is None or profile.messages_analyzed == 0:
            return 'INSUFFICIENT_HISTORY'
        with self.store._conn() as conn:
            source_counts = dict(conn.execute(
                "SELECT provenance,count(*) FROM wa_pr_sources WHERE contact_id=? AND direction='USER' "
                "GROUP BY provenance", (contact_id,)).fetchall())
        reviewed = sum(source_counts.get(p, 0) for p in (
            'VERIFIED_MANUAL_OWNER_SEND', 'USER_EDITED_AI_DRAFT', 'USER_TYPED',
            'VERIFIED_LEGACY_OWNER'))
        strong = sum(source_counts.get(p, 0) for p in (
            'VERIFIED_MANUAL_OWNER_SEND', 'USER_EDITED_AI_DRAFT', 'USER_TYPED'))
        if reviewed == 0:
            return ('DRAFT_READY' if profile.confidence >= .16 and profile.messages_analyzed >= 10
                    and self.store.example_count(contact_id) >= 3 else 'LEGACY_BOOTSTRAP')
        if not self.store.auto_reply_evaluated(contact_id):
            return 'VERIFIED_STYLE_BUILDING' if strong < 20 else 'AUTO_REPLY_CANDIDATE'
        return 'TIMED_AUTO_REPLY_READY'

    def legacy_review_batch(self, contact_id: str, limit: int = 35) -> dict[str, Any]:
        if is_group_chat(contact_id):
            raise ValueError('Only direct contacts can be reviewed')
        return {'contact_id': contact_id, 'examples': self.store.legacy_review_candidates(contact_id, limit)}

    def review_legacy(self, contact_id: str, decisions: dict[str, bool]) -> dict[str, Any]:
        if is_group_chat(contact_id):
            raise ValueError('Only direct contacts can be reviewed')
        counts = self.store.review_legacy_rows(contact_id, decisions)
        if any(counts.values()):
            self._schedule_profile_update(contact_id)
        return {'contact_id': contact_id, **counts, 'maturity': self.maturity(contact_id)}

    def review_legacy_batch(self, contact_id: str, action: str,
                            selected_ids: list[str] | None = None, limit: int = 35) -> dict[str, Any]:
        batch = self.legacy_review_batch(contact_id, limit=min(40, max(1, limit)))
        eligible = {row['message_id'] for row in batch['examples']}
        if action == 'CANCEL':
            return {'contact_id': contact_id, 'status': 'CANCELLED', 'changed': 0}
        if action not in ('APPROVE_ALL', 'APPROVE_SELECTED', 'REJECT_SELECTED'):
            raise ValueError('Unsupported batch review action')
        chosen = eligible if action == 'APPROVE_ALL' else set(selected_ids or [])
        if not chosen or not chosen.issubset(eligible):
            return {'contact_id': contact_id, 'status': 'NEEDS_VALID_SELECTION', 'changed': 0}
        result = self.review_legacy(contact_id, {mid: action != 'REJECT_SELECTED' for mid in chosen})
        return {'status': action, 'changed': len(chosen), **result}

    def verify_manual_owner_send(self, contact_id: str, message_id: str) -> dict[str, Any]:
        """An explicit exact-ID owner attestation, checked against stored inbox and send records."""
        if is_group_chat(contact_id) or not message_id:
            raise ValueError('Direct contact and exact message ID required')
        with self.inbox._get_conn() as conn:
            row = conn.execute("SELECT message_id,chat_id,timestamp,type,text,is_from_me FROM whatsapp_messages "
                               "WHERE message_id=? AND chat_id=?", (message_id, contact_id)).fetchone()
        if not row or not row['is_from_me'] or row['type'] != 'text':
            return {'status': 'NOT_ELIGIBLE'}
        from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import LegacyProvenanceResolver
        resolver = LegacyProvenanceResolver(self.inbox.db_path, self.store.path)
        decision = resolver.classify_live(message_id=message_id, chat_id=contact_id, timestamp=row['timestamp'],
                                          message_type=row['type'], text=row['text'],
                                          source_device_proof='OWNER_ATTESTED_MESSAGE_ID')
        if decision.provenance != Authorship.VERIFIED_MANUAL_OWNER_SEND:
            return {'status': 'NOT_ELIGIBLE', 'reasons': decision.reasons}
        self.store.add_sources(contact_id, [ChatLine(timestamp=row['timestamp'], sender='owner',
            direction=Direction.USER, text=row['text'], message_id=message_id,
            provenance=decision.provenance, provenance_confidence=1.0,
            provenance_reasons=list(decision.reasons))], import_id='owner_attested')
        self._schedule_profile_update(contact_id)
        return {'status': 'VERIFIED_MANUAL_OWNER_SEND', 'message_id': message_id}

    def verify_last_manual_owner_send(self, confirmation: str, contact_id: str = '',
                                      within_seconds: int = 600) -> dict[str, Any]:
        """Resolve an owner's natural attestation to one exact, recent outgoing ID.

        Account direction alone never establishes authorship. Ambiguous or
        recorded JARVIS sends cannot be promoted by this convenience path.
        """
        phrase = ' '.join((confirmation or '').casefold().split())
        if phrase not in ('that last message was mine', 'mark my last reply as manual',
                          'yes i wrote that', 'yes i wrote that.'):
            return {'status': 'NEEDS_OWNER_CONFIRMATION'}
        if contact_id and is_group_chat(contact_id):
            return {'status': 'NOT_ELIGIBLE'}
        cutoff = self.clock() - max(60, min(int(within_seconds), 3600))
        with self.inbox._get_conn() as conn:
            if contact_id:
                rows = conn.execute(
                    "SELECT message_id,chat_id,timestamp,type,text FROM whatsapp_messages "
                    "WHERE is_from_me=1 AND chat_id=? AND timestamp>=? ORDER BY timestamp DESC LIMIT 20",
                    (contact_id, cutoff)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT message_id,chat_id,timestamp,type,text FROM whatsapp_messages "
                    "WHERE is_from_me=1 AND timestamp>=? ORDER BY timestamp DESC LIMIT 20",
                    (cutoff,)).fetchall()
        from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import LegacyProvenanceResolver
        resolver = LegacyProvenanceResolver(self.inbox.db_path, self.store.path)
        candidates = []
        for row in rows:
            if is_group_chat(row['chat_id']) or row['type'] != 'text' or not row['text']:
                continue
            decision = resolver.classify_live(message_id=row['message_id'], chat_id=row['chat_id'],
                timestamp=row['timestamp'], message_type=row['type'], text=row['text'],
                source_device_proof='OWNER_ATTESTED_MESSAGE_ID')
            if decision.provenance == Authorship.VERIFIED_MANUAL_OWNER_SEND:
                candidates.append(row)
        if len(candidates) != 1:
            return {'status': 'NEEDS_CLARIFICATION' if candidates else 'NO_ELIGIBLE_MESSAGE',
                    'candidate_count': len(candidates)}
        row = candidates[0]
        return self.verify_manual_owner_send(row['chat_id'], row['message_id'])

    def _refresh_default_profile(self) -> None:
        lines: list[ChatLine] = []
        for c in self.store.contacts():
            if c["contact_id"] == "__default__":
                continue
            train, _ = self.store.examples(c["contact_id"], splits=("TRAIN",))
            lines += [ChatLine(timestamp=e.timestamp, sender="owner", direction=Direction.USER, text=e.reply,
                               provenance=e.provenance, provenance_confidence=(e.evidence_weight / 0.45 if e.provenance == Authorship.LEGACY_OWNER_LIKELY else 1.0)) for e in train
                      if e.source in (ExampleSource.IMPORT, ExampleSource.LIVE_USER, ExampleSource.USER_EDITED)]
        if lines:
            prof = style_analyzer.default_profile([], lines)
            # Global fallback is statistical style only. Never expose private
            # words, phrases, names, or full examples from another contact.
            for field in ("common_words", "common_tanglish_phrases", "greeting_patterns", "closing_patterns",
                          "acknowledgement_style", "address_terms", "response_patterns", "example_message_ids",
                          "elongation_examples"):
                setattr(prof, field, [])
            prof.shorthand = {}
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

    async def draft_latest(self, contact_id: str) -> dict[str, Any]:
        """Generate and persist a reviewable draft for the latest real direct incoming text."""
        if is_group_chat(contact_id) or self.maturity(contact_id) not in (
            'DRAFT_READY','VERIFIED_STYLE_BUILDING','AUTO_REPLY_CANDIDATE','TIMED_AUTO_REPLY_READY'):
            return {'status': 'INSUFFICIENT_HISTORY'}
        history = self.inbox.get_chat_history(contact_id, limit=100)
        incoming = history[-1] if history else None
        if incoming is None or incoming.is_from_me or incoming.type != 'text' or not incoming.text:
            return {'status': 'NO_UNANSWERED_INCOMING_TEXT'}
        old = self.store.reply_for_message(incoming.message_id)
        if old and old['status'] in ('SUGGESTED','AWAITING_APPROVAL','NEEDS_USER_REVIEW'):
            return {'status': old['status'], 'reply_id': old['id'], 'text': old['text']}
        draft = await self.draft(contact_id, [incoming.text], exclude_message_ids={incoming.message_id})
        candidate = draft['candidate']
        if candidate is None:
            return {'status': _hold_status(draft['answerability'].gate) if draft.get('hold_reason') else 'MODEL_UNAVAILABLE',
                    'reason': draft.get('hold_reason', ''),
                    'answerability': draft['answerability'].category,
                    'required_state': draft['answerability'].gate}
        reply_id = self.store.start_reply(incoming.message_id, [incoming.message_id], contact_id, contact_id,
                                          ReplyMode.SUGGEST_ONLY.value, None, incoming.text)
        if reply_id is None:
            return {'status': 'ALREADY_REVIEWED'}
        quality = draft['quality']
        self.store.update_reply(reply_id, status=Outcome.SUGGESTED.value, text=candidate.text,
                                draft_hash=text_hash(candidate.text), quality=quality.to_dict())
        return {'status': 'SUGGESTED', 'reply_id': reply_id, 'text': candidate.text,
                'quality': quality.to_dict(), 'sent': False}

    def draft_feedback(self, reply_id: int, state: str) -> dict[str, Any]:
        if state not in ('NO_REPLY','BAD_STYLE','WRONG_CONTEXT','REGENERATE'):
            raise ValueError('Unsupported feedback state')
        row = self.store.reply(reply_id)
        if not row or row['status'] not in ('SUGGESTED','AWAITING_APPROVAL','NEEDS_USER_REVIEW'):
            return {'status': 'NOT_REVIEWABLE'}
        self.store.record_draft_feedback(reply_id, row['contact_id'], state, row['text'] or '')
        if state == 'NO_REPLY':
            self.store.update_reply(reply_id, status='REJECTED', reason='owner chose no reply')
        elif state in ('BAD_STYLE','WRONG_CONTEXT'):
            self.store.update_reply(reply_id, reason=state)
        return {'status': state, 'reply_id': reply_id}

    async def regenerate_reply(self, reply_id: int) -> dict[str, Any]:
        row = self.store.reply(reply_id)
        if not row or row['status'] not in ('SUGGESTED','AWAITING_APPROVAL','NEEDS_USER_REVIEW'):
            return {'status': 'NOT_REVIEWABLE'}
        self.store.record_draft_feedback(reply_id, row['contact_id'], 'REGENERATE', row['text'] or '')
        draft = await self.draft(row['contact_id'], [row['incoming']],
                                 exclude_message_ids=set(row['message_ids']))
        candidate = draft['candidate']
        if candidate is None:
            return {'status': 'MODEL_UNAVAILABLE'}
        self.store.update_reply(reply_id, status=Outcome.SUGGESTED.value, text=candidate.text,
                                draft_hash=text_hash(candidate.text), quality=draft['quality'].to_dict())
        return {'status': 'SUGGESTED', 'reply_id': reply_id, 'text': candidate.text, 'sent': False}

    async def test_reply(self, contact_id: str, incoming: str) -> dict[str, Any]:
        """Generate a reply WITHOUT sending (profile quality check)."""
        d = await self.draft(contact_id, [incoming])
        cand, q = d["candidate"], d["quality"]
        policy = self.policy.decide(contact_id, contact_id, has_profile=d["has_profile"], now=self.clock())
        return {"contact_id": contact_id, "incoming": incoming, "reply": cand.text if cand else None,
                "target_language": d["context"].target_language, "understanding": d["understanding"].__dict__,
                "quality": q.to_dict() if q else None,
                "status": ("DRAFT" if cand else _hold_status(d["answerability"].gate)
                           if d.get("hold_reason") else "MODEL_UNAVAILABLE"),
                "answerability": d["answerability"].category, "required_state": d["answerability"].gate,
                "memory_need": d["memory_need"],
                "would_auto_send": bool(policy.auto and cand and q and q.passed
                                        and not d["understanding"].requests_pc_action
                                        and d["modality"].modality != "STICKER_ONLY"),
                "predicted_modality": d["modality"].modality,
                "timing_ms": d.get("timing_ms", {}),
                "examples_used": [{"them": e.example.context, "you": e.example.reply} for e in d["examples"]],
                "sent": False}

    async def evaluate_contact(self, contact_id: str, limit: int = 30) -> dict[str, Any]:
        """Chronological replay with verified and legacy holdouts reported separately."""
        from jarvis.integrations.whatsapp.personal_reply import language as lang
        from jarvis.integrations.whatsapp.personal_reply.modality import observed
        holdout, _ = self.store.examples(contact_id, splits=("HOLDOUT",))
        profile, trained = self.profile_for(contact_id)
        if not trained or not holdout:
            return {"contact_id": contact_id, "samples": 0, "status": "INSUFFICIENT_VERIFIED_HISTORY",
                    "VERIFIED_HOLDOUT": {"samples": 0}, "LEGACY_HOLDOUT": {"samples": 0},
                    "auto_reply_eligible": False}
        reports = {}
        source_lines = self.store.sources(contact_id)
        for label, subset in (
            ('VERIFIED_HOLDOUT', [e for e in holdout if e.provenance in (
                Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND,
                Authorship.USER_EDITED_AI_DRAFT, Authorship.VERIFIED_LEGACY_OWNER)]),
            ('LEGACY_HOLDOUT', [e for e in holdout if e.provenance in (
                Authorship.LEGACY_OWNER_LIKELY, Authorship.USER_APPROVED_AI_DRAFT)]),
        ):
            replay_profile = profile
            if subset:
                cutoff = min(e.timestamp for e in subset)
                replay_profile = style_analyzer.analyze(
                    contact_id, self.store.display_name(contact_id),
                    [line for line in source_lines if line.timestamp < cutoff])
            reports[label] = await self._evaluate_holdout_subset(contact_id, replay_profile, subset, limit)
        verified = reports['VERIFIED_HOLDOUT']
        report = {"contact_id": contact_id, "samples": verified['samples'], "generated": verified['generated'],
                  "profile_confidence": profile.confidence, "VERIFIED_HOLDOUT": verified,
                  "LEGACY_HOLDOUT": reports['LEGACY_HOLDOUT'], "auto_reply_eligible": False,
                  "unsafe_auto_send_count": verified['unsafe_auto_send_count'],
                  **{k: v for k, v in verified.items() if k.endswith('_rate')}}
        # Only verified holdout can support an approval record. Legacy replay is
        # bootstrap diagnostic evidence and never satisfies the auto-send gate.
        with self.store._lock, self.store._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO wa_pr_evaluations "
                         "(contact_id,evaluated_at,samples,metrics_json,approved_at) VALUES (?,?,?,?,NULL)",
                         (contact_id, self.clock(), verified['samples'], json.dumps(report)))
        return report

    async def _evaluate_holdout_subset(self, contact_id: str, profile: ContactStyleProfile,
                                       holdout: list[ReplyExample], limit: int) -> dict[str, Any]:
        from jarvis.integrations.whatsapp.personal_reply import language as lang
        from jarvis.integrations.whatsapp.personal_reply.modality import observed
        counts = {"generated": 0, "clarification_draft": 0, "needs_owner_context": 0, "model_unavailable": 0,
                  "tool_required": 0, "no_reply_needed": 0, "retrieval_invoked": 0, "retrieval_empty": 0,
                  "semantic_pass": 0, "language_match": 0, "emoji_match": 0,
                  "length_match": 0, "modality_match": 0, "unsafe_auto_send": 0,
                  "style_score_sum": 0.0}
        review_case_ids: list[str] = []
        for example in holdout[:max(1, min(limit, 200))]:
            prior = [line for line in self.store.sources(contact_id) if line.timestamp < example.timestamp][-8:]
            thread = [(line.direction == Direction.USER, line.text) for line in prior]
            current = example.context
            answerability = self.answerability_classifier(current, thread)
            from jarvis.integrations.whatsapp.personal_reply.conversation_grounding import missing_owner_status, owner_clarification
            if missing_owner_status(current, thread):
                if owner_clarification(self.store.sources(contact_id), example.timestamp):
                    counts["clarification_draft"] += 1
                else:
                    counts["needs_owner_context"] += 1
                continue
            if answerability.gate != "ANSWERABLE":
                key = "tool_required" if answerability.gate == "REQUIRES_TOOL" else (
                    "no_reply_needed" if answerability.category == "NO_REPLY_NEEDED" else "needs_owner_context")
                counts[key] += 1
                continue
            retrieval_need = memory_need(current, answerability.category)
            if retrieval_need == "MEMORY_NOT_NEEDED":
                retrieved = []
            else:
                counts["retrieval_invoked"] += 1
                retrieved = self.index.retrieve(contact_id, current, k=6, now=example.timestamp)
                counts["retrieval_empty"] += int(not retrieved)
            ctx = build_context(contact_id, self.store.display_name(contact_id), profile, thread, retrieved, [current])
            candidate = await self.generator.generate(ctx, profile)
            if candidate is None:
                counts["model_unavailable"] += 1
                continue
            counts["generated"] += 1
            if (example.provenance in (Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND,
                                       Authorship.USER_EDITED_AI_DRAFT, Authorship.VERIFIED_LEGACY_OWNER)
                    and len(review_case_ids) < 5):
                review_case_ids.append(self.store.save_holdout_review_case(
                    contact_id, current, candidate.text, example.reply, example.timestamp))
            quality = evaluate(candidate, current, ctx.thread_text, ctx.example_text, profile, ctx.target_language,
                               answerability=answerability)
            counts['style_score_sum'] += quality.style_match
            counts["semantic_pass"] += int(quality.semantic_pass and quality.hallucination_risk <= 0.5)
            counts["language_match"] += int(lang.detect(candidate.text).label == lang.detect(example.reply).label)
            counts["emoji_match"] += int(bool(lang.emojis(candidate.text)) == bool(lang.emojis(example.reply)))
            expected_length = max(1, len(example.reply.split()))
            counts["length_match"] += int(abs(len(candidate.text.split()) - expected_length) <= max(2, expected_length // 2))
            counts["modality_match"] += int(observed(candidate.text) == observed(example.reply))
            counts["unsafe_auto_send"] += int(bool(quality.sensitive_topics) and quality.passed)
        n = counts["generated"]
        report = {"samples": len(holdout[:max(1, min(limit, 200))]), "generated": n,
                  **{key + "_rate": round(value / n, 3) if n else None for key, value in counts.items()
                     if key not in ("generated", "clarification_draft", "needs_owner_context", "model_unavailable",
                                    "tool_required", "no_reply_needed", "retrieval_invoked", "retrieval_empty",
                                    "unsafe_auto_send", "style_score_sum")},
                  "clarification_draft": counts["clarification_draft"],
                  "needs_owner_context": counts["needs_owner_context"],
                  "model_unavailable": counts["model_unavailable"],
                  "tool_required": counts["tool_required"],
                  "no_reply_needed": counts["no_reply_needed"],
                  "retrieval_invoked": counts["retrieval_invoked"],
                  "retrieval_empty": counts["retrieval_empty"],
                  "unsafe_auto_send_count": counts["unsafe_auto_send"],
                  "style_score": round(counts['style_score_sum'] / n, 3) if n else None,
                  "review_case_ids": review_case_ids}
        return report

    def approve_offline_evaluation(self, contact_id: str) -> dict[str, Any]:
        if not self.store.approve_offline_evaluation(contact_id):
            return {"status": "REFUSED", "reason": "At least 20 generated holdout replies and zero critical unsafe cases are required"}
        return {"status": "APPROVED_FOR_TIMED_GRANT", "contact_id": contact_id}

    # ------------------------------------------------------------------ grants / modes
    def enable(self, contact_ids: list[str], expires_at: float, everyone: bool = False, names: Optional[list[str]] = None,
               note: str = "", exclude: Optional[list[str]] = None, exclude_names: Optional[list[str]] = None) -> dict[str, Any]:
        now = self.clock()
        if everyone:
            g = self.policy.grant(GrantScope.ALL_DIRECT_CONTACTS, [], expires_at, now=now, note=note)
            left_out = list(dict.fromkeys(exclude or []))
            if left_out:  # an everyone-grant lists the people it leaves out
                self.store.update_grant_contacts(g.grant_id, left_out)
                g.contact_ids = left_out
            but = (" except " + ", ".join(exclude_names or [self.store.display_name(c) for c in left_out])) if left_out else ""
            msg = (f"Auto replies to all direct contacts{but} are on for the next {_duration_words(expires_at - now)} "
                   f"(until {_fmt_until(expires_at)}). Group chats remain disabled.")
        else:
            scope = GrantScope.CONTACT if len(contact_ids) == 1 else GrantScope.CONTACTS
            g = self.policy.grant(scope, contact_ids, expires_at, now=now, note=note)
            who = ", ".join(names or [self.store.display_name(c) for c in contact_ids])
            msg = (f"Auto replies to {who} are enabled for {_duration_words(expires_at - now)} "
                   f"(until {_fmt_until(expires_at)}). Group chats remain disabled.")
            for c in contact_ids:
                self.store.upsert_contact(c)
            self._last_contact = contact_ids[-1]
        self._emit("grant", contact_id=",".join(contact_ids) or "ALL_DIRECT", grant_id=g.grant_id, expires_at=g.expires_at)
        untrained = [] if everyone or g.note else [c for c in contact_ids if self.store.load_profile(c) is None]
        if g.note:
            msg += f' Each person gets: "{away_text(g.note)}"'
        elif everyone and not (self.policy.auto_reply_untrained or g.include_untrained):
            msg += (" People whose style I haven't learned yet get a draft for your OK instead - or tell me what to say, "
                    "like: auto reply to everyone for an hour saying I'm in a meeting.")
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
