"""Unsent semantic, state, role and retrieval checks for the personal reply path."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.example_index import ContactExampleIndex, embed
from jarvis.integrations.whatsapp.personal_reply.models import Authorship, ContactStyleProfile, ReplyCandidate, ReplyExample
from jarvis.integrations.whatsapp.personal_reply.quality_gate import evaluate, validate_semantics
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore
from jarvis.integrations.whatsapp.personal_reply.understand import classify_answerability, memory_need


FROZEN = (
    ("enga iruka?", "PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER"),
    ("saptiya?", "PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER"),
    ("free ah?", "PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER"),
    ("tomorrow varaya?", "OWNER_DECISION_REQUIRED", "REQUIRES_OWNER"),
    ("backend fixed ah?", "JARVIS_KNOWN", "REQUIRES_TOOL"),
    ("meeting 5 ku thaana?", "OWNER_DECISION_REQUIRED", "REQUIRES_OWNER"),
)


@pytest.mark.parametrize("text,category,gate", FROZEN)
def test_frozen_nonanswers_fail_independent_quality_gate(text, category, gate):
    state = classify_answerability(text, [])
    bad = ReplyCandidate(text="seri bro", understood=True, model_confidence=1.0,
                         language_mode="TANGLISH")
    quality = evaluate(bad, text, "", "", ContactStyleProfile(contact_id="test"), "TANGLISH",
                       answerability=state)
    assert (quality.answerability_category, quality.answerability_gate) == (category, gate)
    assert quality.semantic_pass is False and quality.passed is False


@pytest.mark.parametrize("text,category,gate", FROZEN)
def test_frozen_state_probes_hold_before_generation(tmp_path, text, category, gate):
    class NoModel:
        async def chat_json(self, *_args, **_kwargs):
            raise AssertionError("model should not run without trusted state")

    from jarvis.integrations.whatsapp.personal_reply.reply_generator import ReplyGenerator
    class EmptyInbox:
        db_path = None
        def get_chat_history(self, *_args, **_kwargs):
            return []

    agent = PersonalReplyAgent(store=PersonalReplyStore(tmp_path / "style.db"), inbox=EmptyInbox(),
                               generator=ReplyGenerator(client=NoModel()), use_jde=False)
    out = asyncio.run(agent.test_reply("test@s.whatsapp.net", text))
    assert out["reply"] is None and out["would_auto_send"] is False
    assert (out["answerability"], out["required_state"]) == (category, gate)
    assert out["status"] in {"OWNER_INPUT_REQUIRED", "TOOL_REQUIRED"}


@pytest.mark.parametrize("text,category,gate", (
    ("Where r u now?", "PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER"),
    ("saaptingala?", "PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER"),
    ("Are you available now?", "PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER"),
    ("Next week join pannuva?", "OWNER_DECISION_REQUIRED", "REQUIRES_OWNER"),
    ("project status?", "JARVIS_KNOWN", "REQUIRES_TOOL"),
    ("meeting at 7?", "OWNER_DECISION_REQUIRED", "REQUIRES_OWNER"),
    ("₹5000 transfer panriya?", "SENSITIVE", "REQUIRES_OWNER"),
    ("😂😂 loosu", "STYLE_ONLY", "ANSWERABLE"),
    ("that one?", "AMBIGUOUS", "REQUIRES_CLARIFICATION"),
    ("What is the plan?", "AMBIGUOUS", "REQUIRES_CLARIFICATION"),
    ("How are you?", "PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER"),
))
def test_unseen_constructions(text, category, gate):
    state = classify_answerability(text, [])
    assert (state.category, state.gate) == (category, gate)


def test_same_thread_evidence_and_direction_are_separate():
    thread = [(True, "Yes, meeting at 5 confirmed")]
    known = classify_answerability("meeting 5 ku thaana?", thread)
    assert (known.category, known.gate) == ("CONVERSATION_KNOWN", "ANSWERABLE")
    assert classify_answerability("meeting 6 ku thaana?", thread).gate == "REQUIRES_OWNER"
    assert classify_answerability("Backend fixed.", [(True, "Please update me")]).category == "STYLE_ONLY"
    assert classify_answerability("Backend update?", []).gate == "REQUIRES_TOOL"
    assert classify_answerability("Update?", []).gate == "REQUIRES_OWNER"
    candidate = ReplyCandidate(text="okay", understood=True, model_confidence=0.99, language_mode="TANGLISH")
    passed, reason, _ = validate_semantics(candidate, "meeting 5 ku thaana?", "You: Yes, meeting at 5 confirmed", known)
    assert not passed and "answer" in reason
    changed_time = ReplyCandidate(text="meeting at 6 confirmed", understood=True,
                                  model_confidence=0.99, language_mode="TANGLISH")
    passed, reason, _ = validate_semantics(changed_time, "meeting 5 ku thaana?",
                                           "You: Yes, meeting at 5 confirmed", known)
    assert not passed and "time" in reason


def test_question_roles_and_updates():
    # The current incoming speaker is the contact; past owner lines are the
    # only thread evidence allowed to ground a confirmation.
    owner_asks = classify_answerability("Backend fixed.", [(True, "Is the backend fixed?")])
    assert owner_asks.category == "STYLE_ONLY"
    contact_asks = classify_answerability("backend update?", [])
    assert contact_asks.who_asked == "CONTACT" and contact_asks.who_must_answer == "OWNER"
    assert contact_asks.gate == "REQUIRES_TOOL"
    contact_provides = classify_answerability("Backend fixed.", [])
    assert contact_provides.category == "STYLE_ONLY"
    contact_asks_owner = classify_answerability("meeting 5 ku thaana?", [(False, "meeting maybe 5")])
    assert contact_asks_owner.gate == "REQUIRES_OWNER"
    owner_confirms = classify_answerability("meeting 5 ku thaana?", [(True, "meeting at 5 confirmed")])
    assert owner_confirms.gate == "ANSWERABLE"
    owner_questions_contact = classify_answerability("Backend fixed.", [(True, "Backend update sollu")])
    assert owner_questions_contact.category == "STYLE_ONLY"
    assert classify_answerability("What is the plan?", [(False, "I have a question")]).gate == "REQUIRES_CLARIFICATION"


def test_style_score_cannot_rescue_empty_or_wrong_direction_answer():
    profile = ContactStyleProfile(contact_id="test", median_message_length=2)
    bad = ReplyCandidate(text="seri bro", understood=True, model_confidence=1.0, language_mode="TANGLISH")
    result = evaluate(bad, "free ah?", "", "", profile, "TANGLISH")
    assert not result.semantic_pass and not result.passed
    known = classify_answerability("backend update?", [(True, "Backend fixed")])
    backwards = ReplyCandidate(text="update sollu bro", understood=True, model_confidence=1.0, language_mode="TANGLISH")
    passed, reason, _ = validate_semantics(backwards, "backend update?", "You: Backend fixed", known)
    assert not passed and "direction" in reason


def test_memory_can_be_skipped_and_weak_results_are_zero(tmp_path):
    assert memory_need("seri", "NO_REPLY_NEEDED") == "MEMORY_NOT_NEEDED"
    assert memory_need("remember that hotel?", "STYLE_ONLY") == "EPISODIC_REFERENCE_REQUIRED"
    store = PersonalReplyStore(tmp_path / "style.db")
    ex = ReplyExample(contact_id="a@s.whatsapp.net", context="nav bar change git push",
                      reply="checking", timestamp=10, provenance=Authorship.VERIFIED_LEGACY_OWNER,
                      evidence_weight=0.5)
    store.add_example(ex, embed([ex.context])[0])
    index = ContactExampleIndex(store)
    assert index.retrieve("a@s.whatsapp.net", "where did you eat lunch?", now=20) == []
    assert index.retrieve("b@s.whatsapp.net", "nav bar change git push", now=20) == []


def test_holdout_semantic_rating_is_separate_from_style(tmp_path):
    store = PersonalReplyStore(tmp_path / "ratings.db")
    cid = "same-contact@s.whatsapp.net"
    case_id = store.save_holdout_review_case(cid, "Where are you?", "seri bro", "At home", 10)
    assert store.rate_holdout_review_case(cid, case_id, "WRONG_MEANING",
                                          {"semantic_correct": False, "dyadic_correct": True,
                                           "language_match": True, "emoji_appropriate": True,
                                           "length_appropriate": False})
    case = store.holdout_review_cases(cid)[0]
    assert case["rating"] == "WRONG_MEANING"
    assert case["dimensions"]["semantic_correct"] is False
    assert case["dimensions"]["dyadic_correct"] is True
