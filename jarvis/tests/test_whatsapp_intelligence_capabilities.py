"""Registered capability boundaries, persistent dispatch and real resource identity."""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from jarvis.core.commands.provenance import owner_command
from jarvis.memory.working_memory import WorkingMemory
from jarvis.integrations.whatsapp.intelligence.engine import ThreadIntelligence
from jarvis.integrations.whatsapp.intelligence.models import AttachmentRef, MessageRef
from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.whatsapp_intelligence import WhatsAppIntelligenceTool
from jarvis.tests.test_whatsapp_intelligence import A, B, context, message, ingest


@pytest.fixture
def setup(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    engine = ThreadIntelligence(inbox)
    inbox.intelligence = engine
    engine.client = object()  # No external providers are contacted.
    ingest(engine, message("contact-a", "hello"))
    ingest(engine, message("contact-b", "hello", B))
    return engine, WorkingMemory(), ToolRegistry()


def tool(setup, operation):
    engine, memory, registry = setup
    result = WhatsAppIntelligenceTool(operation)
    result.inbox, result.working_memory, result.registry = engine.inbox, memory, registry
    return result


@pytest.mark.asyncio
async def test_routing_arguments_cannot_invent_owner_evidence(setup):
    token = owner_command.set("Draft a reply to Naveen")
    try:
        result = await tool(setup, "draft_create").arun({"contact": A, "text": "I will pay 900 tomorrow"})
        assert not result["result"]["draft"]["validation"]["passed"]
    finally:
        owner_command.reset(token)


@pytest.mark.asyncio
async def test_literal_owner_content_revision_and_stale_send(setup):
    token = owner_command.set("Draft this for Naveen: Meet at 7")
    try:
        result = await tool(setup, "draft_create").arun({"contact": A, "text": "Meet at 7"})
    finally:
        owner_command.reset(token)
    draft = result["result"]["draft"]
    assert draft["validation"]["passed"]
    assert setup[1].context.pending_draft.draft_id == draft["id"]
    ingest(setup[0], message("new", "Are you there?"))
    with pytest.raises(ValueError, match="Conversation changed"):
        await tool(setup, "draft_send").arun({"revision": 1})


@pytest.mark.asyncio
async def test_concurrent_draft_submission_claims_once(setup):
    engine, memory, registry = setup
    draft = await engine.draft(A, "hello")
    operation = tool(setup, "draft_send")
    operation.remember(A, "Naveen", draft)
    calls = []

    class Sender:
        def run(self, arguments):
            calls.append(arguments)
            time.sleep(0.05)
            return {"status": "SENT", "message_id": "verified-receipt", "evidence": {"transport_ack": True}}

    registry.get = lambda name: Sender()
    results = await asyncio.gather(operation.arun({"revision": 1}), operation.arun({"revision": 1}), return_exceptions=True)
    assert len(calls) == 1
    assert engine.store.get(draft.id)["status"] == "SENT"
    assert any(isinstance(result, ValueError) for result in results)


@pytest.mark.asyncio
async def test_cancel_never_submits(setup):
    draft = await setup[0].draft(A, "hello")
    operation = tool(setup, "draft_cancel")
    operation.remember(A, "Naveen", draft)
    assert (await operation.arun({}))["status"] == "CANCELLED"
    assert setup[1].context.pending_draft is None
    with pytest.raises(ValueError):
        setup[0].validate_draft(draft.id, 1)


def test_durable_dispatch_concurrency_and_thread_serialization(setup):
    store = setup[0].store
    for msg in (message("a1", "hello"), message("a2", "world"), message("b1", "hello", B)):
        store.enqueue_dispatch(msg)
    with ThreadPoolExecutor(max_workers=3) as pool:
        claims = list(pool.map(lambda _: store.claim_dispatch(), range(3)))
    assert {row["message_id"] for row in claims if row} == {"a1", "b1"}
    store.finish_dispatch("a1")
    assert store.claim_dispatch()["message_id"] == "a2"
    setup[0].recover()
    assert store.claim_dispatch() is None


def test_placeholder_cannot_consume_decrypted_dispatch(setup):
    store = setup[0].store
    placeholder = message("same", "", state="PENDING_DECRYPTION")
    store.enqueue_dispatch(placeholder)
    store.enqueue_dispatch(message("same", "decrypted"))
    first = store.claim_dispatch()
    store.finish_dispatch(first["message_id"])
    second = store.claim_dispatch()
    assert {first["message_id"], second["message_id"]} == {"pending:same", "same"}


@pytest.mark.asyncio
async def test_typed_ordinal_does_not_select_other_contact(setup):
    engine, memory, _ = setup
    operation = tool(setup, "attachment_search")
    for number in (1, 2):
        engine.store.put("ATTACHMENT", AttachmentRef(id=f"att{number}", thread_id=A, message_id="contact-a", filename=f"file{number}.pdf"))
    await operation.arun({"contact": A})
    resolve = tool(setup, "reference_resolve")
    result = await resolve.arun({"resource_kind": "ATTACHMENT", "ordinal": 2})
    assert memory.get_selected_resource().canonical_identifier == result["result"]["resource"]["id"]
    with pytest.raises(ValueError, match="thread"):
        await resolve.arun({"contact": B, "resource_kind": "ATTACHMENT", "ordinal": 2})


def test_capability_metadata_registers_after_late_tool_injection(setup, monkeypatch):
    from jarvis.core.capabilities import registry as module
    monkeypatch.setattr(module, "_GLOBAL_CAPABILITY_REGISTRY", None)
    catalog = module.get_default_capability_registry()
    setup[2].register(tool(setup, "draft_create"))
    assert module.get_default_capability_registry(setup[2]) is catalog
    assert catalog.get_by_tool("whatsapp_draft_create").input_schema["properties"]


def test_relative_date_needs_source_day(setup):
    from jarvis.integrations.whatsapp.intelligence.engine import ClaimGroundingValidator
    evidence = context("Meeting tomorrow")
    evidence.current.timestamp = time.time() - 86400 * 3
    assert "STALE_RELATIVE_DATE" in ClaimGroundingValidator().validate("Meeting tomorrow", evidence).reasons


@pytest.mark.asyncio
async def test_correction_old_number_cannot_survive(setup):
    draft = await setup[0].draft(A, "Meet at 5", "Meet at 5, actually 5:30")
    assert "EXCLUSION_VIOLATED" in draft.validation.reasons
    corrected = await setup[0].draft(A, "Meet at 5:30", "Meet at 5, actually 5:30")
    assert "EXCLUSION_VIOLATED" not in corrected.validation.reasons


@pytest.mark.asyncio
async def test_negative_command_cannot_claim_send_even_if_classifier_selects_it(setup):
    draft = await setup[0].draft(A, "hello")
    operation = tool(setup, "draft_send")
    operation.remember(A, "Naveen", draft)
    token = owner_command.set("Don't send it")
    try:
        with pytest.raises(ValueError, match="Negative owner"):
            await operation.arun({"revision": 1})
    finally:
        owner_command.reset(token)
    assert setup[0].store.get(draft.id)["status"] == "DRAFT"


def test_edited_message_invalidates_derived_question_and_vectors(setup):
    engine = setup[0]
    ingest(engine, message("edited", "Where is the file?"))
    with engine.store.connection() as conn:
        conn.execute("INSERT INTO wa_vectors VALUES(?,?,?,?)", ("edited", A, "configured", "[1,0]"))
    ingest(engine, message("edited", "Found the file"))
    assert engine.store.get("item:edited")["status"] == "SUPERSEDED"
    with engine.store.connection() as conn:
        assert conn.execute("SELECT count(*) FROM wa_vectors WHERE message_id='edited'").fetchone()[0] == 0


def test_finished_old_job_cannot_hide_new_revision(setup):
    engine = setup[0]
    engine.persist(message("edited", "original"))
    job = next(job for job in engine.store.pending_jobs() if job["message_id"] == "edited")
    engine.persist(message("edited", "updated"))
    engine.store.finish_job("edited", True, job["event_revision"])
    assert any(row["message_id"] == "edited" for row in engine.store.pending_jobs())


def test_lexicon_needs_confirmation_or_repeated_consistent_observations(setup):
    store = setup[0].store
    store.learn_term("fooz", "tomorrow")
    assert "fooz" not in store.lexicon()
    assert not store.learn_term("fooz", "yesterday")
    store.learn_term("fooz", "tomorrow")
    store.learn_term("fooz", "tomorrow")
    assert store.lexicon()["fooz"] == "tomorrow"


def test_doc_extraction_has_thread_provenance_and_images_are_interpretations(setup):
    from jarvis.integrations.whatsapp.intelligence.engine import ClaimGroundingValidator
    evidence = context("report attached")
    evidence.attachments = [AttachmentRef(id="att", thread_id=A, message_id="m1", downloaded=True,
        mime_type="application/pdf", extracted_text="Invoice total 700")]
    assert ClaimGroundingValidator().validate("Invoice total 700", evidence).passed
    evidence.attachments[0].mime_type = "image/jpeg"
    assert not ClaimGroundingValidator().validate("Invoice total 700", evidence).passed
    evidence.attachments[0].mime_type = "application/pdf"
    evidence.attachments[0].thread_id = B
    assert "CROSS_THREAD_EVIDENCE" in ClaimGroundingValidator().validate("Invoice total 700", evidence).reasons


@pytest.mark.asyncio
async def test_global_pause_resume_retains_original_grant_expiration(setup, tmp_path):
    from types import SimpleNamespace
    from jarvis.integrations.whatsapp.personal_reply.auto_reply_policy import AutoReplyPolicy
    from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore
    from jarvis.integrations.whatsapp.personal_reply.crypto import DataBox
    from jarvis.integrations.whatsapp.personal_reply.models import GrantScope
    store = PersonalReplyStore(tmp_path / "personal.db", box=DataBox(use_keyring=False))
    policy = AutoReplyPolicy(store)
    grant = policy.grant(GrantScope.CONTACTS, [A], time.time() + 60)
    pause, resume = tool(setup, "autoreply_pause"), tool(setup, "autoreply_resume")
    pause.personal_reply = resume.personal_reply = SimpleNamespace(policy=policy)
    await pause.arun({})
    assert policy.decide(A, A, True).reason == "PAUSED"
    await resume.arun({})
    # Resuming a grant preserves its expiry; it cannot bypass the separate
    # verified offline-evaluation gate for generated replies.
    assert policy.decide(A, A, True).reason == "OFFLINE_EVALUATION_REQUIRED"
    assert policy.active_grants()[0].expires_at == grant.expires_at


def test_read_only_connection_does_not_advertise_sending(setup):
    from types import SimpleNamespace
    send = tool(setup, "send_media")
    send.transport = SimpleNamespace(is_connected=True, read_only=True)
    assert not send.availability()
    download = tool(setup, "attachment_download")
    download.transport = send.transport
    assert download.availability()


def test_requested_capability_aliases_are_executable_metadata(setup):
    from jarvis.tools.system.whatsapp_intelligence import create_intelligence_tools
    registry = setup[2]
    for capability in create_intelligence_tools():
        registry.register(capability)
        assert registry.get(capability.capability_metadata()["id"]) is capability
    assert registry.contains("whatsapp.message.reply_context")
    assert registry.contains("whatsapp.message.action_items")


@pytest.mark.asyncio
async def test_registered_status_label_is_not_a_message_recipient(setup):
    from jarvis.core.router.router import SmartRouter
    setup[2].register(tool(setup, "status"))
    router = SmartRouter(tool_registry=setup[2], working_memory=setup[1])
    decision = await router.route("whatsapp status")
    assert decision.intent == "whatsapp_status" and decision.slots == {}


@pytest.mark.asyncio
async def test_main_migration_does_not_create_a_second_message_store(tmp_path):
    import sqlite3
    from jarvis.core.persistence.writer import PersistenceWriter
    path = tmp_path / "main.db"
    writer = PersistenceWriter(path)
    try:
        await writer.start()
        with sqlite3.connect(path) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 10
            assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='wa_events'").fetchone() is None
        with sqlite3.connect(path.with_name("main.before_schema_000.db")) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        await writer.close()


@pytest.mark.asyncio
async def test_generated_draft_gets_one_guarded_repair(setup):
    class Model:
        calls = 0
        async def chat_json(self, messages, schema, **kwargs):
            if "speech_act" in schema.get("properties", {}):
                return {"speech_act": "GREETING", "confidence": .95, "topic_message_ids": []}
            self.calls += 1
            return {"text": "I will pay 900 tomorrow" if self.calls == 1 else "Could you clarify that?"}
    model = Model()
    setup[0].client = model
    draft = await setup[0].draft(A)
    assert model.calls == 2
    assert draft.validation.passed and draft.content == "Could you clarify that?"
