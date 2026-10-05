"""Offline acceptance of durable same-thread context and conservative send gates."""
import asyncio
import json
import time

import pytest

from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.integrations.whatsapp.intelligence.engine import ThreadIntelligence, ClaimGroundingValidator
from jarvis.integrations.whatsapp.intelligence.models import ContactRef, ThreadRef, ConversationContext, MessageRef, SemanticMessageFrame
from jarvis.integrations.whatsapp.intelligence.language import semantic_frame, TanglishNormalizer, reply_necessity

A = "919000000001@s.whatsapp.net"
B = "919000000002@s.whatsapp.net"


@pytest.fixture
def engine(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    engine = ThreadIntelligence(inbox)
    inbox.intelligence = engine
    return engine


def message(mid, text, thread=A, **kwargs):
    return NormalizedWhatsAppMessage(message_id=mid, chat_id=thread, sender_id=thread,
        text=text, timestamp=str(time.time() - 10), **kwargs)


def ingest(engine, msg):
    engine.inbox.add_message(msg)
    for job in engine.store.pending_jobs():
        engine.process_job(job)
        engine.store.finish_job(job["message_id"])


def test_additive_backup_and_restart(engine):
    ingest(engine, message("m1", "Please send the project file"))
    assert engine.store.db_path.with_name("inbox.before_intelligence_009.db").is_file()
    other = ThreadIntelligence(engine.inbox)
    assert other.context(A).recent[0].id == "m1"
    assert other.store.resources(A, "ITEM")[0]["message_id"] == "m1"


def test_duplicate_history_replay_does_not_stale_draft(engine):
    msg = message("m1", "hello")
    assert engine.persist(msg)
    assert not engine.persist(msg.model_copy(update={"history": True}))
    assert engine.store.version(A) == 1


def test_identity_cannot_cross_contacts(engine):
    assert engine.persist(message("m1", "secret"))
    with pytest.raises(ValueError, match="thread"):
        engine.persist(message("m1", "secret", B))
    engine.store.put("LINK", {"id": "link:m1", "thread_id": A, "url": "https://example.org"})
    with pytest.raises(ValueError, match="identity"):
        engine.store.put("LINK", {"id": "link:m1", "thread_id": B, "url": "https://example.org"})


def test_quoted_and_historical_retrieval_are_thread_scoped(engine):
    ingest(engine, message("old", "project budget 700"))
    ingest(engine, message("private", "project budget 900 secret", B))
    ingest(engine, message("current", "What about that project?", reply_to={"message_id": "old"}))
    ctx = engine.context(A, "project", "current")
    assert ctx.reply_chain[0].id == "old"
    assert all(r.thread_id == A for r in [*ctx.recent, *ctx.historical, *ctx.reply_chain])
    assert "budget 900 secret" not in ctx.model_dump_json()


def test_context_budget(engine):
    ingest(engine, message("long", "please " * 4000))
    ctx = engine.context(A, "please " * 4000, "long")
    assert len(ctx.model_dump_json()) <= engine.MAX_CONTEXT_CHARS


def test_draft_revisions_cancel_stale_and_recovery(engine):
    draft = asyncio.run(engine.draft(A, "Meet at 7"))
    assert engine.validate_draft(draft.id, 1).id == draft.id
    edited = asyncio.run(engine.edit(draft.id, "", "Meet at 8"))
    assert edited.id == draft.id and edited.revision == 2
    with pytest.raises(ValueError, match="changed"):
        engine.validate_draft(draft.id, 1)
    assert engine.validate_draft(draft.id, 2).content == "Meet at 8"
    ingest(engine, message("new", "Are you there?"))
    with pytest.raises(ValueError, match="Conversation changed"):
        engine.validate_draft(draft.id, 2)
    edited.status = "STARTED"
    engine.store.put("DRAFT", edited)
    engine.recover()
    assert engine.store.get(draft.id)["status"] == "UNCERTAIN"


def test_group_draft_cannot_send(engine):
    draft = asyncio.run(engine.draft("123@g.us", "hello"))
    with pytest.raises(ValueError, match="direct"):
        engine.validate_draft(draft.id, 1)


def test_watcher_ignores_history_and_own_and_fires_once(engine):
    from jarvis.integrations.whatsapp.intelligence.models import Watcher
    engine.store.put("WATCHER", Watcher(id="watch", thread_id=A, kind="KEYWORD", keyword="budget", expires_at=time.time()+60))
    ingest(engine, message("history", "budget", history=True))
    ingest(engine, message("own", "budget", is_from_me=True))
    assert engine.store.get("watch")["status"] == "ACTIVE"
    ingest(engine, message("live", "budget"))
    assert engine.store.get("watch")["matched_message_id"] == "live"
    ingest(engine, message("live2", "budget"))
    assert engine.store.get("watch")["matched_message_id"] == "live"


def test_generated_echo_is_not_user_style(engine):
    engine.store.generated(A, "hello", "r1", "out1")
    engine.persist(message("out1", "hello", is_from_me=True))
    with engine.store.connection() as conn:
        assert conn.execute("SELECT authorship FROM wa_events WHERE message_id='out1'").fetchone()[0] == "JARVIS"


def context(text):
    return ConversationContext(contact=ContactRef(id=A), thread=ThreadRef(id=A),
        frame=SemanticMessageFrame(thread_id=A, raw_text=text, normalized_text=text),
        current=MessageRef(id="m1", thread_id=A, text=text))


# 100 adversarial cases: unsupported numbers, invented commitments, swapped
# participants, negation removal, and recombination of two observed facts.
ADVERSARIAL = []
for n in range(20):
    ADVERSARIAL.extend([
        (f"Meeting at {n+1}", f"Meeting at {n+101}"),
        (f"Can you send file {n}?", f"I will send file {n}"),
        (f"Naveen paid Ashok {n}", f"Ashok paid Naveen {n}"),
        (f"Do not approve invoice {n}", f"Approve invoice {n}"),
        (f"Meeting {n} Tuesday. Invoice {n+1} Friday", f"Meeting {n} Friday"),
    ])


@pytest.mark.parametrize("evidence,reply", ADVERSARIAL)
def test_adversarial_claims_require_review(evidence, reply):
    assert not ClaimGroundingValidator().validate(reply, context(evidence)).passed


def test_grounded_extract_and_explicit_owner_text_pass():
    validator = ClaimGroundingValidator()
    assert validator.validate("Meeting at 7", context("Meeting at 7")).passed
    assert validator.validate("I will send the file tomorrow", context("hello"), "I will send the file tomorrow").passed
    assert not validator.validate("salary 700", context("salary 700"), exclusions=["salary"]).passed


@pytest.mark.parametrize("text,act", [("ena panra?", "QUESTION"), ("epdi iruka?", "QUESTION"),
    ("file anupidu please", "REQUEST"), ("pls anupu report", "REQUEST"), ("send panna venam", "NEGATION"),
    ("do not send", "NEGATION"), ("okay", "ACK"), ("thanks", "ACK")])
def test_linguistic_holdout(text, act):
    assert semantic_frame(A, text, time.time()).speech_act == act


def test_no_reply_ack_and_temporal_anchor():
    assert reply_necessity(semantic_frame(A, "okay", time.time())) == "NO_REPLY_NEEDED"
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ts = datetime(2026, 10, 2, 12, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()
    frame = semantic_frame(A, "naalaiku", ts)
    assert "2026-10-03" in frame.temporal_expressions[0]["value"]
