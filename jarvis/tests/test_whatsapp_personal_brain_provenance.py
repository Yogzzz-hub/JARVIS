"""Provenance and isolation checks for the personal communication brain."""
from __future__ import annotations

import asyncio
import numpy as np
import pytest

from jarvis.integrations.whatsapp.personal_reply import importer, style_analyzer
from jarvis.integrations.whatsapp.personal_reply.auto_reply_policy import AutoReplyPolicy
from jarvis.integrations.whatsapp.personal_reply.models import (
    Authorship, ChatLine, ContactStyleProfile, Direction, GrantScope, ReplyCandidate, ReplyMode,
)
from jarvis.integrations.whatsapp.personal_reply.quality_gate import evaluate
from jarvis.integrations.whatsapp.personal_reply.sticker_memory import StickerMemory
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


CONTACT = "111@lid"


def test_unknown_and_generated_outgoing_never_become_style_evidence():
    lines = [
        ChatLine(1, "contact", Direction.CONTACT, "tomorrow?", message_id="in"),
        ChatLine(2, "owner", Direction.USER, "unknown", message_id="unknown"),
        ChatLine(3, "owner", Direction.USER, "auto", message_id="auto", provenance=Authorship.AUTO_GENERATED),
        ChatLine(4, "owner", Direction.USER, "yes bro", message_id="typed", reply_to="in",
                 provenance=Authorship.USER_TYPED),
    ]
    assert [e.reply for e in importer.build_examples(CONTACT, lines)] == ["yes bro"]
    profile = style_analyzer.analyze(CONTACT, "Test", lines)
    assert profile.messages_analyzed == 1
    assert "unknown" not in profile.common_words and "auto" not in profile.common_words


def test_chronological_holdout_never_enters_training_index(tmp_path):
    store = PersonalReplyStore(tmp_path / "brain.db")
    lines = []
    for i in range(20):
        lines += [ChatLine(i * 10, "contact", Direction.CONTACT, f"question {i}", message_id=f"in{i}"),
                  ChatLine(i * 10 + 1, "owner", Direction.USER, f"answer {i}", message_id=f"out{i}",
                           provenance=Authorship.USER_TYPED)]
    examples = importer.build_examples(CONTACT, lines)
    assert [e.split for e in examples] == ["TRAIN"] * 15 + ["HOLDOUT"] * 5
    store.replace_examples(CONTACT, examples, np.zeros((20, 1024), dtype=np.float32))
    from jarvis.integrations.whatsapp.personal_reply.example_index import ContactExampleIndex
    retrieved, _ = ContactExampleIndex(store)._load(CONTACT)
    assert len(retrieved) == 15 and all(e.split == "TRAIN" for e in retrieved)


def test_old_examples_and_profiles_fail_closed_after_migration(tmp_path):
    store = PersonalReplyStore(tmp_path / "brain.db")
    with store._conn() as conn:
        conn.execute("INSERT INTO wa_pr_profiles(contact_id,display_name,profile_enc,profile_version,updated_at,provenance_verified) "
                     "VALUES(?,?,?,?,?,0)", (CONTACT, "Test", "unverified", 1, 1))
        conn.execute("INSERT INTO wa_pr_examples(contact_id,context_enc,reply_enc,ts,source,split,vector,created_at) "
                     "VALUES(?,?,?,?,?,?,?,?)", (CONTACT, "old", "old", 1, "IMPORT", "TRAIN", b"", 1))
    assert store.load_profile(CONTACT) is None
    assert store.examples(CONTACT)[0] == []


def test_old_reply_cannot_ground_new_factual_claim():
    profile = style_analyzer.analyze(CONTACT, "Test", [ChatLine(1, "owner", Direction.USER, "okay",
                                                  provenance=Authorship.USER_TYPED)])
    report = evaluate(ReplyCandidate(text="I will pay 5000", understood=True, model_confidence=0.9,
                                     language_mode="ENGLISH"), "hi", "", "I will pay 5000", profile, "ENGLISH")
    assert report.hallucination_risk > 0 and not report.passed


def test_sticker_memory_requires_owner_provenance_and_stays_in_contact(tmp_path):
    store = PersonalReplyStore(tmp_path / "brain.db")
    sticker = tmp_path / "sticker.webp"
    sticker.write_bytes(b"RIFFfake-webp")
    memory = StickerMemory(store)
    with pytest.raises(ValueError):
        memory.index_owner_send(message_id="m1", contact_id=CONTACT, media_path=str(sticker),
                                preceding_context="funny joke")
    digest = memory.index_owner_send(message_id="m1", contact_id=CONTACT, media_path=str(sticker),
                                     preceding_context="funny joke", provenance=Authorship.USER_TYPED, sent_at=1)
    assert memory.index_owner_send(message_id="m1", contact_id=CONTACT, media_path=str(sticker),
                                   preceding_context="funny joke", provenance=Authorship.USER_TYPED, sent_at=1) == digest
    assert len(memory.candidates(CONTACT, "funny joke", "CASUAL")) == 1
    assert memory.candidates("222@lid", "funny joke", "CASUAL") == []
    memory.record_actual_use(digest)
    assert memory.candidates(CONTACT, "funny joke", "CASUAL") == []


def test_live_auto_reply_requires_offline_evaluation_even_with_grant(tmp_path):
    store = PersonalReplyStore(tmp_path / "brain.db")
    policy = AutoReplyPolicy(store)
    policy.grant(GrantScope.CONTACT, [CONTACT], expires_at=1000, now=1)
    assert policy.decide(CONTACT, CONTACT, has_profile=True, now=2).mode == ReplyMode.SUGGEST_ONLY


def test_source_import_dedupes_within_batch_and_on_repeat(tmp_path):
    store = PersonalReplyStore(tmp_path / "brain.db")
    line = ChatLine(10, "owner", Direction.USER, "okay bro", provenance=Authorship.USER_TYPED)
    assert store.add_sources(CONTACT, [line, line]) == 1
    assert store.add_sources(CONTACT, [line]) == 0


def test_holdout_replay_is_offline_and_cannot_clear_auto_gate(tmp_path):
    from tests.whatsapp_personal.harness import make_agent
    from tests.whatsapp_personal.synthetic import export_text
    agent = make_agent(tmp_path)
    agent.import_chat(CONTACT, "Test", export_text=export_text("yoga", n=40), verified_fixture=True)
    result = asyncio.run(agent.evaluate_contact(CONTACT, limit=2))
    assert result["samples"] == 2 and result["auto_reply_eligible"] is False
    assert agent.store.auto_reply_evaluated(CONTACT) is False
    assert agent.transport.sent_messages == []


def test_modality_prediction_uses_owner_rates_and_blocks_sensitive_stickers():
    from jarvis.integrations.whatsapp.personal_reply.modality import observed, predict
    profile = ContactStyleProfile(contact_id=CONTACT, messages_analyzed=40,
                                  modality_counts={"TEXT": 8, "TEXT_EMOJI": 25, "STICKER_ONLY": 7})
    assert observed("okay 😀") == "TEXT_EMOJI"
    assert predict(profile, "CASUAL").modality == "TEXT_EMOJI"
    assert predict(profile, "URGENT", sticker_candidates=[{"score": 0.9, "sticker_hash": "x"}]).modality == "TEXT"
