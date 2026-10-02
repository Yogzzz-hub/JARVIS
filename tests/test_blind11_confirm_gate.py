"""The Blind-11 harness may say "yes" for the owner only to let an already-correct sandboxed action run - a confirmation
never rescues a wrong tool, target, recipient, scope, negation or forbidden action."""
from tests.blind11.runner import auto_confirm_gate

DELETE = {"id": "g", "should_act": True, "outcome": "action", "capabilities": ["delete_file"],
          "slots": {"delete_file": {"path": ["temp_test.txt"]}}, "confirmation": "required",
          "exec": {"kind": "file", "post": [{"missing": "Desktop/temp_test.txt"}]}}


def _gate(case, pending, executed=(), earlier=0, last=True):
    return auto_confirm_gate(case, case.get("exec") or {}, last, [(t, a, "pending") for t, a in pending], list(executed), earlier)


def test_correct_sandboxed_action_is_approved():
    ok, gate = _gate(DELETE, [("delete_file", {"path": "temp_test.txt"})])
    assert ok and not gate["refused"]


def test_wrong_target_is_never_approved():
    ok, gate = _gate(DELETE, [("delete_file", {"path": "everything"})])
    assert not ok and "2_tool_target_slots_already_match" in gate["refused"]


def test_wrong_tool_is_never_approved():
    ok, _ = _gate(DELETE, [("move_file", {"source": "temp_test.txt", "destination": "Documents"})])
    assert not ok


def test_case_that_must_not_act_is_never_approved():
    case = {**DELETE, "should_act": False, "outcome": "clarify", "capabilities": [], "forbidden_capabilities": ["delete_file"]}
    ok, gate = _gate(case, [("delete_file", {"path": "everything"})])
    assert not ok and "1_oracle_expects_this_action" in gate["refused"]


def test_not_sandboxed_is_never_approved():
    case = {**DELETE, "capabilities": ["send_whatsapp_message"], "slots": {"send_whatsapp_message": {"recipient": ["arun"]}},
            "exec": {}}
    ok, gate = _gate(case, [("send_whatsapp_message", {"recipient": "Arun", "message": "hi"})])
    assert not ok and "4_entirely_sandboxed" in gate["refused"]


def test_confirmation_not_required_by_oracle_is_not_approved():
    ok, gate = _gate({**DELETE, "confirmation": "none"}, [("delete_file", {"path": "temp_test.txt"})])
    assert not ok and "3_oracle_requires_confirmation" in gate["refused"]


def test_forbidden_action_already_executed_blocks_approval():
    case = {**DELETE, "forbidden_capabilities": ["empty_recycle_bin"]}
    ok, gate = _gate(case, [("delete_file", {"path": "temp_test.txt"})], executed=[("empty_recycle_bin", {}, "real")])
    assert not ok and "5_no_forbidden_capability" in gate["refused"]


def test_only_one_pending_confirmation():
    ok, _ = _gate(DELETE, [("delete_file", {"path": "temp_test.txt"}), ("delete_file", {"path": "temp_test.txt"})])
    assert not ok
    ok, gate = _gate(DELETE, [("delete_file", {"path": "temp_test.txt"})], earlier=1)
    assert not ok and "6_exactly_one_pending_confirmation" in gate["refused"]
