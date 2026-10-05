from types import SimpleNamespace

from scripts.stage25_conversation_state import PendingInteraction, resolve_from_working_context, resolve_short_reply


def pending(kind="CONFIRMATION", **changes):
    values = dict(kind=kind, reference_id="ticket-1", created_at=1000.0, channel="desktop", owner_id="user-1", action_fingerprint="action-sha")
    values.update(changes)
    return PendingInteraction(**values)


def resolve(text, confirmation=None, clarification=None, **changes):
    values = dict(channel="desktop", owner_id="user-1", now=1001.0)
    values.update(changes)
    return resolve_short_reply(text, pending_confirmation=confirmation, pending_clarification=clarification, **values)


def test_unbound_yes_is_no_action_across_scripts():
    for text in ("yes", "seri", "ok", "ama", "சரி", "ஆம்"):
        result = resolve(text)
        assert result.resolution == "NO_ACTION"
        assert result.should_execute is False


def test_valid_ticket_is_identified_without_execution():
    result = resolve("சரி!", pending())
    assert (result.speech_act, result.resolution, result.reference_id, result.action_fingerprint) == ("CONFIRMATION", "CONFIRM_PENDING", "ticket-1", "action-sha")
    assert result.should_execute is False


def test_pending_clarification_takes_priority_over_confirmation():
    result = resolve("yes", pending(), pending("CLARIFICATION", reference_id="clarify-1"))
    assert (result.resolution, result.reference_id) == ("CLARIFICATION_RESPONSE", "clarify-1")


def test_stale_mismatched_consumed_or_unbound_tickets_cannot_confirm():
    for ticket, changes in (
        (pending(created_at=900), {}),
        (pending(channel="whatsapp"), {}),
        (pending(owner_id="other"), {}),
        (pending(consumed=True), {}),
        (pending(action_fingerprint=""), {}),
        (pending(reference_id=""), {}),
        (pending(), {"now": 999}),
    ):
        assert resolve("yes", ticket, **changes).resolution == "NO_ACTION"


def test_negative_reply_rejects_exact_pending_ticket():
    assert resolve("இல்லை", pending()).resolution == "REJECT_PENDING"


def test_longer_request_and_questions_are_not_short_confirmation():
    for text in ("yes send the file", "yes? send panna mudiyuma", "I said yes earlier", "send panna venam"):
        assert resolve(text, pending()) is None


def test_working_context_adapter_requires_bound_pending_records():
    context = SimpleNamespace(pending_confirmation=SimpleNamespace(ticket_id="ticket-1"), pending_clarification=None)
    assert resolve_from_working_context("yes", context, channel="desktop", owner_id="user-1", now=1001).resolution == "NO_ACTION"
    context.pending_confirmation = pending()
    assert resolve_from_working_context("yes", context, channel="desktop", owner_id="user-1", now=1001).reference_id == "ticket-1"
