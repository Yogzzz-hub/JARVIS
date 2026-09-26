"""REST endpoints for Dashboard -> WhatsApp -> Contacts (local gateway only; browser origins are rejected
by the gateway middleware). All mutating calls act only on the owner's own configuration."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from jarvis.integrations.whatsapp.personal_reply.dedupe import is_group_chat
from jarvis.integrations.whatsapp.personal_reply.importer import ImportError_
from jarvis.integrations.whatsapp.personal_reply.models import ReplyMode


class ImportBody(BaseModel):
    export_text: str = ""
    display_name: str = ""
    from_inbox: bool = False
    owner_name: str = ""


class TextBody(BaseModel):
    text: str


class ModeBody(BaseModel):
    mode: str
    minutes: Optional[float] = None


class MinutesBody(BaseModel):
    minutes: float


class FeedbackBody(BaseModel):
    kind: str


class ApproveBody(BaseModel):
    text: Optional[str] = None
    mark_good: bool = False


class ContactBody(BaseModel):
    contact: str          # number, JID or saved contact name
    display_name: str = ""


def _agent(runtime: Any):
    service = getattr(runtime, "whatsapp_service", None)
    agent = getattr(service, "personal_reply", None) if service is not None else None
    if agent is None:
        from jarvis.integrations.whatsapp.personal_reply.agent import get_personal_reply_agent
        agent = get_personal_reply_agent()
    return agent


def _cid(contact_id: str) -> str:
    if is_group_chat(contact_id):
        raise HTTPException(400, "Group chats are not supported by personal replies.")
    return contact_id


def register(app: FastAPI, runtime: Any) -> None:
    base = "/whatsapp/personal"

    @app.get(f"{base}/contacts")
    async def contacts() -> dict[str, Any]:
        a = _agent(runtime)
        return {"contacts": a.contacts_overview(), "grants": a.policy.status(), "activity": a.store.recent_activity(60),
                "encryption": a.store.box.status, "status_text": a.status_text()}

    @app.post(f"{base}/contacts")
    async def add_contact(body: ContactBody) -> dict[str, Any]:
        a = _agent(runtime)
        raw = body.contact.strip()
        if "@" in raw:
            cid, name = raw, body.display_name
        elif sum(ch.isdigit() for ch in raw) >= 8:
            cid, name = "".join(ch for ch in raw if ch.isdigit()) + "@s.whatsapp.net", body.display_name
        else:
            from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
            contact, ambiguous, prompt = ContactResolver().resolve(raw)
            if ambiguous or contact is None:
                raise HTTPException(409, prompt or "Contact not found.")
            cid, name = contact.jid, body.display_name or contact.display_name
        a.store.upsert_contact(_cid(cid), name)
        return {"contact_id": cid, "display_name": name or cid.split("@")[0]}

    @app.get(base + "/contacts/{contact_id}")
    async def detail(contact_id: str) -> dict[str, Any]:
        a = _agent(runtime)
        row = next((c for c in a.contacts_overview() if c["contact_id"] == contact_id), None)
        prof = a.store.load_profile(_cid(contact_id))
        return {"contact": row, "profile": prof.to_dict() if prof else None, "summary": prof.summary() if prof else None,
                "versions": a.store.profile_versions(contact_id), "examples": a.store.example_count(contact_id),
                "sources": a.store.source_count(contact_id)}

    @app.post(base + "/contacts/{contact_id}/import")
    async def import_chat(contact_id: str, body: ImportBody) -> dict[str, Any]:
        try:
            return _agent(runtime).import_chat(_cid(contact_id), body.display_name, export_text=body.export_text,
                                               from_inbox=body.from_inbox, owner_name=body.owner_name)
        except ImportError_ as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post(base + "/contacts/{contact_id}/rebuild")
    async def rebuild(contact_id: str) -> dict[str, Any]:
        return _agent(runtime).rebuild_profile(_cid(contact_id))

    @app.get(base + "/contacts/{contact_id}/preview")
    async def preview(contact_id: str) -> dict[str, Any]:
        return await _agent(runtime).preview_style(_cid(contact_id))

    @app.post(base + "/contacts/{contact_id}/test")
    async def test_reply(contact_id: str, body: TextBody) -> dict[str, Any]:
        return await _agent(runtime).test_reply(_cid(contact_id), body.text)

    @app.post(base + "/contacts/{contact_id}/mode")
    async def set_mode(contact_id: str, body: ModeBody) -> dict[str, Any]:
        a = _agent(runtime)
        cid = _cid(contact_id)
        try:
            if body.mode == ReplyMode.AUTO_REPLY_UNTIL.value:
                if not body.minutes or body.minutes <= 0:
                    raise HTTPException(400, "Auto-reply needs a duration.")
                return a.enable([cid], a.clock() + body.minutes * 60)
            return a.set_mode(cid, ReplyMode(body.mode))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post(base + "/contacts/{contact_id}/stop")
    async def stop(contact_id: str) -> dict[str, Any]:
        return _agent(runtime).stop(_cid(contact_id))

    @app.post(f"{base}/everyone")
    async def everyone(body: MinutesBody) -> dict[str, Any]:
        a = _agent(runtime)
        try:
            return a.enable([], a.clock() + body.minutes * 60, everyone=True)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post(f"{base}/stop_all")
    async def stop_all() -> dict[str, Any]:
        return _agent(runtime).stop_all()

    @app.delete(base + "/contacts/{contact_id}/profile")
    async def clear(contact_id: str) -> dict[str, Any]:
        return _agent(runtime).clear_profile(_cid(contact_id))

    @app.get(base + "/contacts/{contact_id}/history")
    async def history(contact_id: str) -> dict[str, Any]:
        return {"history": _agent(runtime).history(_cid(contact_id))}

    @app.post(base + "/contacts/{contact_id}/feedback")
    async def feedback(contact_id: str, body: FeedbackBody) -> dict[str, Any]:
        try:
            return _agent(runtime).feedback(_cid(contact_id), body.kind)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post(base + "/replies/{reply_id}/approve")
    async def approve(reply_id: int, body: ApproveBody) -> dict[str, Any]:
        return await _agent(runtime).approve_reply(reply_id, edited_text=body.text, mark_good=body.mark_good)

    @app.post(base + "/replies/{reply_id}/reject")
    async def reject(reply_id: int) -> dict[str, Any]:
        return _agent(runtime).reject_reply(reply_id)
