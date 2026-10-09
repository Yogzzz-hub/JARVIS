"""Plan validity: a well-formed TaskGraph is still rejected when it does not fit the request (negation, exclusion,
rejection, policy, unrequested destructive step, unsafe literal target). New constructions, not Blind-11 sentences."""
from __future__ import annotations

import pytest

from jarvis.core.planner.schema import TaskGraph, TaskNode
from jarvis.core.planner.semantic_validator import semantic_errors


def _g(*steps) -> TaskGraph:
    return TaskGraph(goal="test", nodes=[TaskNode(id=f"n{i + 1}", tool=t, args=a) for i, (t, a) in enumerate(steps)])


def _codes(graph, text):
    return {e.code for e in semantic_errors(graph, text)}


def test_a_plan_that_fits_the_request_is_clean():
    g = _g(("find_file", {"query": "budget"}), ("send_whatsapp_message", {"recipient": "Anu", "message": "here"}))
    assert _codes(g, "find the budget file and send it to Anu") == set()


def test_negated_action_cannot_come_back_through_the_planner():
    g = _g(("find_file", {"query": "invoice"}), ("send_whatsapp_message", {"recipient": "Ravi", "message": "x"}))
    assert "NEGATED_ACTION" in _codes(g, "find the invoice, but don't send it to anyone")


def test_negation_is_scoped_to_its_object():
    g = _g(("open_app", {"name": "chrome"}))
    assert "NEGATED_ACTION" not in _codes(g, "don't open spotify, open chrome")
    g = _g(("open_app", {"name": "spotify"}))
    assert "NEGATED_ACTION" in _codes(g, "don't open spotify, open chrome")


def test_excluded_recipient_is_never_a_target():
    g = _g(("send_whatsapp_message", {"recipient": "Lakshmi", "message": "running late"}))
    assert "EXCLUDED_TARGET" in _codes(g, "tell everyone I'm running late, except Lakshmi")


def test_rejected_alternative_is_never_used():
    g = _g(("open_file", {"path": "report_final.png"}))
    assert "REJECTED_VALUE" in _codes(g, "open the report pdf, not the png")


def test_must_never_requests_have_no_plan():
    g = _g(("browser_click", {"target": "pay now"}))
    assert "POLICY_VIOLATION" in _codes(g, "pay 4000 rupees to the landlord on phonepe")


@pytest.mark.parametrize("tool,args", [("delete_file", {"path": "old.log"}), ("send_whatsapp_message", {"recipient": "A", "message": "b"}),
                                       ("system_power_control", {"action": "shutdown"}), ("uninstall_software", {"name": "vlc"})])
def test_destructive_or_outward_step_needs_a_request_for_it(tool, args):
    g = _g(("find_file", {"query": "notes"}), (tool, args))
    assert "UNREQUESTED_ACTION" in _codes(g, "find my notes and show them to me")


def test_literal_destructive_target_goes_through_the_scope_guard(tmp_path, monkeypatch):
    home = tmp_path
    (home / "Desktop").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    g = _g(("delete_file", {"path": str(home / "Desktop")}))
    assert "DESTRUCTIVE_TARGET" in _codes(g, "delete the old backup from my desktop")
