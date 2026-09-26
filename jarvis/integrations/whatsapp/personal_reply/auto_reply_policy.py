"""Who may be answered automatically, until when, and in which mode.

* Groups are blocked structurally, before any model runs (``dedupe.is_group_chat``).
* Auto-reply exists only as an explicit, time-boxed ``AutoReplyGrant`` created by the owner.
  There is no permanent auto mode unless ``allow_permanent`` is configured.
* A grant stops being honoured the instant ``now >= expires_at`` (checked on every decision, and a
  background task also revokes it and tells the UI).
* ``stop_all()`` is the global emergency stop: it revokes every grant and blocks in-flight sends.
* Per-contact base modes (OFF / SUGGEST_ONLY / ASK_BEFORE_SEND) apply when no grant is active.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from jarvis.integrations.whatsapp.personal_reply.dedupe import is_group_chat
from jarvis.integrations.whatsapp.personal_reply.models import AutoReplyGrant, GrantScope, ReplyMode
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore

MAX_GRANT_HOURS = 24.0


@dataclass
class PolicyDecision:
    mode: ReplyMode
    reason: str
    grant: Optional[AutoReplyGrant] = None

    @property
    def auto(self) -> bool:
        return self.mode == ReplyMode.AUTO_REPLY_UNTIL


class AutoReplyPolicy:
    def __init__(self, store: PersonalReplyStore, auto_reply_untrained: bool = False, allow_permanent: bool = False,
                 max_hours: float = MAX_GRANT_HOURS) -> None:
        self.store = store
        self.auto_reply_untrained = auto_reply_untrained
        self.allow_permanent = allow_permanent
        self.max_hours = max_hours
        self._stop_generation = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ grants
    def grant(self, scope: GrantScope, contact_ids: list[str], expires_at: float, now: Optional[float] = None,
              include_untrained: bool = False) -> AutoReplyGrant:
        now = time.time() if now is None else now
        if expires_at <= now:
            raise ValueError("The auto-reply window must end in the future.")
        if not self.allow_permanent and expires_at - now > self.max_hours * 3600 + 1:
            raise ValueError(f"Auto-reply can be enabled for at most {self.max_hours:g} hours at a time.")
        if scope != GrantScope.ALL_DIRECT_CONTACTS and not contact_ids:
            raise ValueError("Choose at least one contact.")
        if any(is_group_chat(c) for c in contact_ids if scope != GrantScope.ALL_DIRECT_CONTACTS):
            raise ValueError("Group chats can never receive automatic replies.")
        g = AutoReplyGrant(grant_id=f"grant_{uuid.uuid4().hex[:10]}", scope=scope,
                           contact_ids=list(dict.fromkeys(contact_ids)) if scope != GrantScope.ALL_DIRECT_CONTACTS else [],
                           enabled_at=now, expires_at=expires_at, mode=ReplyMode.AUTO_REPLY_UNTIL, granted_by_user=True,
                           include_untrained=include_untrained)
        self.store.add_grant(g)
        return g

    def active_grants(self, now: Optional[float] = None) -> list[AutoReplyGrant]:
        now = time.time() if now is None else now
        return [g for g in self.store.grants() if g.active(now)]

    def expire_due(self, now: Optional[float] = None) -> list[AutoReplyGrant]:
        """Revoke grants whose window has ended (returns them so the UI / voice can say so)."""
        now = time.time() if now is None else now
        expired = [g for g in self.store.grants() if g.revoked_at is None and g.expires_at <= now]
        for g in expired:
            self.store.revoke_grant(g.grant_id, at=g.expires_at)
        return expired

    def stop_contact(self, contact_id: str) -> int:
        """'Stop replying to her': removes this contact from every active grant immediately."""
        changed = 0
        for g in self.store.grants():
            if g.revoked_at is not None or not g.covers(contact_id):
                continue
            if g.scope == GrantScope.ALL_DIRECT_CONTACTS:
                self.store.update_grant_contacts(g.grant_id, g.contact_ids + [contact_id])  # exclusion
            else:
                remaining = [c for c in g.contact_ids if c != contact_id]
                if remaining:
                    self.store.update_grant_contacts(g.grant_id, remaining)
                else:
                    self.store.revoke_grant(g.grant_id)
            changed += 1
        if self.store.get_mode(contact_id) != ReplyMode.OFF:
            self.store.set_mode(contact_id, ReplyMode.OFF)
        return changed

    def stop_all(self) -> int:
        """Global emergency stop."""
        with self._lock:
            self._stop_generation += 1
        n = 0
        for g in self.store.grants():
            if g.revoked_at is None:
                self.store.revoke_grant(g.grant_id)
                n += 1
        return n

    @property
    def stop_generation(self) -> int:
        return self._stop_generation

    # ------------------------------------------------------------------ decisions
    def decide(self, contact_id: str, chat_id: str, has_profile: bool, now: Optional[float] = None) -> PolicyDecision:
        now = time.time() if now is None else now
        if is_group_chat(chat_id) or is_group_chat(contact_id):
            return PolicyDecision(ReplyMode.OFF, "GROUP_BLOCKED")
        self.expire_due(now)
        grants = [g for g in self.active_grants(now) if g.covers(contact_id)]
        if grants:
            g = max(grants, key=lambda x: x.expires_at)
            if g.scope == GrantScope.ALL_DIRECT_CONTACTS and not has_profile and not (self.auto_reply_untrained or g.include_untrained):
                return PolicyDecision(ReplyMode.SUGGEST_ONLY, "UNTRAINED_CONTACT_EVERYONE_MODE", g)
            return PolicyDecision(ReplyMode.AUTO_REPLY_UNTIL, "GRANT_ACTIVE", g)
        base = self.store.get_mode(contact_id)
        if base == ReplyMode.AUTO_REPLY_UNTIL:  # an auto mode without a live grant is never honoured
            base = ReplyMode.OFF
        return PolicyDecision(base, "BASE_MODE" if base != ReplyMode.OFF else "NOT_ENABLED")

    def still_allowed(self, decision: PolicyDecision, stop_generation: int, now: Optional[float] = None) -> bool:
        """Re-check right before sending (expiry or STOP may have happened while drafting)."""
        if stop_generation != self._stop_generation:
            return False
        if decision.grant is None:
            return True
        now = time.time() if now is None else now
        current = next((g for g in self.store.grants() if g.grant_id == decision.grant.grant_id), None)
        return bool(current and current.active(now))

    def status(self, now: Optional[float] = None) -> list[dict]:
        now = time.time() if now is None else now
        out = []
        for g in self.active_grants(now):
            out.append({"grant_id": g.grant_id, "scope": g.scope.value, "contact_ids": g.contact_ids,
                        "expires_at": g.expires_at, "minutes_left": max(0, round((g.expires_at - now) / 60)),
                        "groups": "BLOCKED"})
        return out
