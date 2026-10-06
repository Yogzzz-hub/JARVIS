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


class FileBody(BaseModel):
    filename: str = ""
    content_base64: str = ""    # a file (zip / txt / json / csv) from the dashboard's file picker
    text: str = ""              # or pasted text in any supported format
    contact_id: str = ""
    display_name: str = ""
    owner_name: str = ""


class TextBody(BaseModel):
    text: str


class ModeBody(BaseModel):
    mode: str
    minutes: Optional[float] = None
    note: str = ""  # optional away message ("I'm in a meeting") sent once instead of a drafted reply


class MinutesBody(BaseModel):
    minutes: float
    note: str = ""


class FeedbackBody(BaseModel):
    kind: str


class ApproveBody(BaseModel):
    text: Optional[str] = None
    mark_good: bool = False


class LegacyReviewBody(BaseModel):
    decisions: dict[str, bool]


class LegacyBatchActionBody(BaseModel):
    action: str
    selected_ids: list[str] = []
    limit: int = 35


class ManualConfirmationBody(BaseModel):
    confirmation: str
    contact_id: str = ""


class HoldoutRatingBody(BaseModel):
    rating: str
    semantic_correct: bool | None = None
    dyadic_correct: bool | None = None
    language_match: bool | None = None
    emoji_appropriate: bool | None = None
    length_appropriate: bool | None = None


class ContactBody(BaseModel):
    contact: str          # number, JID or saved contact name
    display_name: str = ""


class BrainBuildBody(BaseModel):
    scope: str = 'ALL'
    contact_id: str = ''


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

    @app.get(base + '/intelligence/overview')
    async def brain_overview() -> dict[str, Any]:
        a = _agent(runtime)
        def read() -> dict[str, Any]:
            with a.inbox._get_conn() as con:
                messages = con.execute('SELECT count(*) FROM whatsapp_messages').fetchone()[0]
                direct = con.execute("SELECT count(DISTINCT chat_id) FROM whatsapp_messages WHERE "
                                     "chat_id LIKE '%@lid' OR chat_id LIKE '%@s.whatsapp.net' OR chat_id LIKE '%@c.us'").fetchone()[0]
                groups = con.execute("SELECT count(DISTINCT chat_id) FROM whatsapp_messages WHERE chat_id LIKE '%@g.us'").fetchone()[0]
                try:
                    observed_live = con.execute("SELECT count(*) FROM wa_events WHERE "
                                                "json_extract(payload,'$.history')=0").fetchone()[0]
                except Exception:
                    observed_live = 0
            with a.store._conn() as con:
                profiles = con.execute('SELECT count(*) FROM wa_pr_profiles WHERE contact_id!=?', ('__default__',)).fetchone()[0]
                indexed = con.execute('SELECT count(*) FROM wa_brain_contact_state').fetchone()[0]
                pairs = con.execute('SELECT count(*) FROM wa_pr_examples').fetchone()[0]
                imported = con.execute("SELECT EXISTS(SELECT 1 FROM wa_pr_sources WHERE import_id NOT IN "
                                       "('live','owner_attested','reviewed_draft'))").fetchone()[0]
            service = getattr(runtime, 'whatsapp_service', None)
            connected = bool(service and getattr(getattr(service, 'transport', None), 'is_connected', False))
            from jarvis.core.language_shadow import get_language_service
            return {'messages_stored': messages, 'direct_contacts': direct, 'groups': groups,
                    'connection': 'READY' if connected else 'DEGRADED',
                    'python_listener': bool(service),
                    'profiles_ready': profiles, 'contacts_indexed': indexed, 'reply_pairs': pairs,
                    'history': {'live_history_capture': 'OBSERVED' if observed_live else 'UNKNOWN',
                                'observed_live_events': observed_live,
                                'local_history_available': messages > 0,
                                'imported_history_available': bool(imported),
                                'remote_history_complete': 'UNKNOWN'},
                    'memory': a.store.brain_state(), 'latest_job': a.brain_jobs.latest(),
                    'generated_auto_reply_enabled': False,
                    'language_layer': {'source': 'Unified JARVIS NLP', 'shadow': get_language_service().enabled(),
                                       'controls_tools': False, 'personal_style_source': 'Personal Reply Brain'}}
        return await __import__('asyncio').to_thread(read)

    @app.post(base + '/intelligence/jobs')
    async def start_brain_job(body: BrainBuildBody) -> dict[str, Any]:
        a = _agent(runtime)
        try:
            return a.brain_jobs.start(body.scope.upper(), _cid(body.contact_id) if body.contact_id else '')
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get(base + '/intelligence/jobs/{job_id}')
    async def brain_job(job_id: str) -> dict[str, Any]:
        try:
            return _agent(runtime).brain_jobs.get(job_id)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown intelligence job') from exc

    @app.post(base + '/intelligence/jobs/{job_id}/cancel')
    async def cancel_brain_job(job_id: str) -> dict[str, Any]:
        try:
            return _agent(runtime).brain_jobs.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown intelligence job') from exc

    @app.get(base + '/intelligence/contacts/{contact_id}')
    async def brain_contact(contact_id: str) -> dict[str, Any]:
        cid = _cid(contact_id)
        return _agent(runtime).store.brain_state(cid)

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

    @app.post(base + "/import-file")
    async def import_file(body: FileBody) -> dict[str, Any]:
        import base64
        try:
            data: bytes | str = base64.b64decode(body.content_base64) if body.content_base64 else body.text
        except ValueError as exc:
            raise HTTPException(400, "content_base64 is not valid base64") from exc
        if body.contact_id:
            _cid(body.contact_id)
        try:
            return {"results": _agent(runtime).import_file(data, body.filename, contact_id=body.contact_id,
                                                           display_name=body.display_name, owner_name=body.owner_name)}
        except ImportError_ as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post(base + "/feed/import")
    async def import_feed() -> dict[str, Any]:
        return _agent(runtime).import_feed_folder()

    @app.post(base + "/contacts/{contact_id}/rebuild")
    async def rebuild(contact_id: str) -> dict[str, Any]:
        return _agent(runtime).rebuild_profile(_cid(contact_id))

    @app.post(base + "/refresh-all")
    async def refresh_all() -> dict[str, Any]:
        return _agent(runtime).refresh_all()

    @app.get(base + "/contacts/{contact_id}/style/explain")
    async def explain_style(contact_id: str) -> dict[str, Any]:
        return _agent(runtime).explain_style(_cid(contact_id))

    @app.post(base + "/contacts/{contact_id}/style/evaluate")
    async def evaluate_style(contact_id: str) -> dict[str, Any]:
        return await _agent(runtime).evaluate_contact(_cid(contact_id))

    @app.post(base + "/contacts/{contact_id}/style/approve-evaluation")
    async def approve_evaluation(contact_id: str) -> dict[str, Any]:
        return _agent(runtime).approve_offline_evaluation(_cid(contact_id))

    @app.get(base + "/contacts/{contact_id}/style/holdout-review")
    async def holdout_review(contact_id: str) -> dict[str, Any]:
        cid = _cid(contact_id)
        return {'contact_id': cid, 'cases': _agent(runtime).store.holdout_review_cases(cid)}

    @app.post(base + "/contacts/{contact_id}/style/holdout-review/{case_id}")
    async def rate_holdout(contact_id: str, case_id: str, body: HoldoutRatingBody) -> dict[str, Any]:
        try:
            dimensions = body.model_dump(exclude={'rating'}, exclude_none=True)
            saved = _agent(runtime).store.rate_holdout_review_case(_cid(contact_id), case_id, body.rating,
                                                                  dimensions)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {'status': 'SAVED' if saved else 'NOT_FOUND', 'case_id': case_id}

    @app.get(base + "/contacts/{contact_id}/maturity")
    async def maturity(contact_id: str) -> dict[str, Any]:
        a = _agent(runtime)
        return {'contact_id': contact_id, 'state': a.maturity(_cid(contact_id))}

    @app.get(base + "/contacts/{contact_id}/legacy-review")
    async def legacy_review_batch(contact_id: str, limit: int = 35) -> dict[str, Any]:
        return _agent(runtime).legacy_review_batch(_cid(contact_id), limit=min(40, max(1, limit)))

    @app.post(base + "/contacts/{contact_id}/legacy-review")
    async def legacy_review(contact_id: str, body: LegacyReviewBody) -> dict[str, Any]:
        return _agent(runtime).review_legacy(_cid(contact_id), body.decisions)

    @app.post(base + "/contacts/{contact_id}/legacy-review/action")
    async def legacy_review_action(contact_id: str, body: LegacyBatchActionBody) -> dict[str, Any]:
        return _agent(runtime).review_legacy_batch(
            _cid(contact_id), body.action, body.selected_ids, body.limit)

    @app.post(base + "/contacts/{contact_id}/manual-send/{message_id}/verify")
    async def verify_manual(contact_id: str, message_id: str) -> dict[str, Any]:
        return _agent(runtime).verify_manual_owner_send(_cid(contact_id), message_id)

    @app.post(base + "/manual-send/verify-last")
    async def verify_last_manual(body: ManualConfirmationBody) -> dict[str, Any]:
        return _agent(runtime).verify_last_manual_owner_send(
            body.confirmation, _cid(body.contact_id) if body.contact_id else '')

    @app.post(base + "/contacts/{contact_id}/draft-latest")
    async def draft_latest(contact_id: str) -> dict[str, Any]:
        return await _agent(runtime).draft_latest(_cid(contact_id))

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
                return a.enable([cid], a.clock() + body.minutes * 60, note=body.note)
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
            return a.enable([], a.clock() + body.minutes * 60, everyone=True, note=body.note)
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

    @app.post(base + "/replies/{reply_id}/feedback")
    async def draft_feedback(reply_id: int, body: FeedbackBody) -> dict[str, Any]:
        if body.kind == 'REGENERATE':
            return await _agent(runtime).regenerate_reply(reply_id)
        return _agent(runtime).draft_feedback(reply_id, body.kind)
