import json
import pytest
from pathlib import Path
from pydantic import BaseModel

from jarvis.security.confirmation.manager import ConfirmationManager, compute_action_fingerprint
from jarvis.security.confirmation.models import TicketStatus
from jarvis.security.paths import canonicalize_path, is_protected_path, verify_toctou
from jarvis.security.policy.evaluator import PolicyEvaluator
from jarvis.security.policy.models import PolicyDecisionType, PolicyReasonCode
from jarvis.tools.base import Contract, RiskLevel, ToolDefinition

class DummyInput(Contract):
    pass

class DummyOutput(Contract):
    pass

def create_mock_tool_def(name: str, risk: RiskLevel, tags: tuple[str, ...] = ()) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="mock tool",
        input_model=DummyInput,
        output_model=DummyOutput,
        read_only=(risk == RiskLevel.READ_ONLY),
        risk=risk,
        tags=tags,
    )

def test_policy_evaluator_defaults():
    evaluator = PolicyEvaluator()
    
    # Read-only auto-allows
    t_ro = create_mock_tool_def("test_ro", RiskLevel.READ_ONLY)
    dec = evaluator.evaluate_node(t_ro, {"query": "sample"})
    assert dec.decision == PolicyDecisionType.ALLOW
    assert dec.reason_code == PolicyReasonCode.DEFAULT_ALLOW

    # External effect requires confirmation
    t_ext = create_mock_tool_def("test_ext", RiskLevel.EXTERNAL_EFFECT)
    dec = evaluator.evaluate_node(t_ext, {"to": "someone@example.com"})
    assert dec.decision == PolicyDecisionType.REQUIRE_CONFIRMATION
    assert dec.reason_code == PolicyReasonCode.EXTERNAL_EFFECT_CONFIRM

    # Destructive requires confirmation
    t_destr = create_mock_tool_def("test_destr", RiskLevel.DESTRUCTIVE)
    dec = evaluator.evaluate_node(t_destr, {"path": "C:\\Users\\ashok\\Desktop\\tmp.txt"})
    assert dec.decision == PolicyDecisionType.REQUIRE_CONFIRMATION
    assert dec.reason_code == PolicyReasonCode.DESTRUCTIVE_CONFIRM

def test_protected_paths_and_traversal():
    evaluator = PolicyEvaluator()
    t_destr = create_mock_tool_def("test_destr", RiskLevel.DESTRUCTIVE)

    # Protected root: Windows
    dec = evaluator.evaluate_node(t_destr, {"path": "C:\\Windows\\System32\\cmd.exe"})
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.reason_code == PolicyReasonCode.PROTECTED_PATH

    # Protected root: Program Files
    dec = evaluator.evaluate_node(t_destr, {"path": "C:\\Program Files\\App\\app.exe"})
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.reason_code == PolicyReasonCode.PROTECTED_PATH

    # Traversal attack: ..\..\Windows
    dec = evaluator.evaluate_node(t_destr, {"path": "C:\\Users\\ashok\\Documents\\..\\..\\Windows\\explorer.exe"})
    assert dec.decision == PolicyDecisionType.DENY
    assert dec.reason_code == PolicyReasonCode.PROTECTED_PATH

def test_uac_and_auth_pauses():
    evaluator = PolicyEvaluator()
    t_uac = create_mock_tool_def("test_uac", RiskLevel.PRIVILEGED, tags=("uac_required",))
    dec = evaluator.evaluate_node(t_uac, {"installer": "setup.exe"})
    assert dec.decision == PolicyDecisionType.PAUSE_FOR_USER
    assert dec.reason_code == PolicyReasonCode.UAC_REQUIRED

    t_auth = create_mock_tool_def("test_auth", RiskLevel.PRIVILEGED, tags=("auth_required",))
    dec = evaluator.evaluate_node(t_auth, {"url": "https://secure.site"})
    assert dec.decision == PolicyDecisionType.PAUSE_FOR_USER
    assert dec.reason_code == PolicyReasonCode.AUTHENTICATION_REQUIRED

def test_raw_shell_and_powershell_denial():
    evaluator = PolicyEvaluator()
    t_cmd = create_mock_tool_def("test_cmd", RiskLevel.PRIVILEGED)

    dec_shell = evaluator.evaluate_node(t_cmd, {"command": "whoami", "shell": True})
    assert dec_shell.decision == PolicyDecisionType.DENY
    assert dec_shell.reason_code == PolicyReasonCode.RAW_SHELL_DENIED

    dec_ps = evaluator.evaluate_node(t_cmd, {"powershell_raw": "Get-Service"})
    assert dec_ps.decision == PolicyDecisionType.DENY
    assert dec_ps.reason_code == PolicyReasonCode.POWERSHELL_UNREGISTERED

def test_confirmation_ticket_lifecycle():
    cm = ConfirmationManager(default_timeout_s=2.0)
    args = {"path": "C:\\Users\\ashok\\Desktop\\old.txt"}
    fp = compute_action_fingerprint("delete_file", args, graph_id="g1", node_id="n1")

    ticket = cm.issue_ticket(
        request_id="r1",
        graph_id="g1",
        node_id="n1",
        tool_name="delete_file",
        args=args,
        risk=RiskLevel.DESTRUCTIVE,
    )

    # Initial pending ticket cannot be consumed
    valid, err = cm.consume_ticket(ticket.ticket_id, fp)
    assert not valid
    assert "not approved" in err

    # Approve ticket
    assert cm.approve_ticket(ticket.ticket_id)

    # Changed args cannot reuse ticket
    changed_fp = compute_action_fingerprint("delete_file", {"path": "C:\\Users\\ashok\\Desktop\\different.txt"})
    valid, err = ticket.is_valid_for(changed_fp)
    assert not valid
    assert "materially changed" in err

    # Proper consumption
    consumed, msg = cm.consume_ticket(ticket.ticket_id, fp)
    assert consumed

    # Consumed ticket cannot be reused
    reused, r_err = cm.consume_ticket(ticket.ticket_id, fp)
    assert not reused
    assert "already been consumed" in r_err

def test_golden_dataset_validation():
    golden_file = Path(__file__).resolve().parent.parent.parent / "tests" / "data" / "policy_golden.jsonl"
    assert golden_file.exists()

    evaluator = PolicyEvaluator()
    with open(golden_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) >= 200, f"Expected at least 200 scenarios, got {len(lines)}"

    checked = 0
    for item in lines:
        cat = item.get("category")
        if "expected_decision" in item:
            risk = RiskLevel(item["risk"])
            t_def = create_mock_tool_def(item["tool"], risk)
            dec = evaluator.evaluate_node(t_def, item["args"])
            assert dec.decision.value == item["expected_decision"], f"Scenario {item['id']} failed decision"
            if "expected_reason" in item:
                assert dec.reason_code.value == item["expected_reason"], f"Scenario {item['id']} failed reason"
            checked += 1

    assert checked >= 170
