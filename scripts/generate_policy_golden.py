import json
from pathlib import Path

OUT_FILE = Path(__file__).resolve().parent.parent / "tests" / "data" / "policy_golden.jsonl"
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

scenarios = []

# 1. READ_ONLY ALLOWED (20)
for i in range(20):
    scenarios.append({
        "id": f"ro_allow_{i+1:03d}",
        "category": "read_only_allowed",
        "tool": "find_file" if i % 2 == 0 else "list_dir",
        "args": {"query": f"doc_{i}.txt"} if i % 2 == 0 else {"path": f"C:\\Users\\Public\\Folder_{i}"},
        "risk": "READ_ONLY",
        "expected_decision": "ALLOW",
        "expected_reason": "DEFAULT_ALLOW",
        "requires_confirmation": False
    })

# 2. REVERSIBLE ALLOWED (20)
for i in range(20):
    scenarios.append({
        "id": f"rev_allow_{i+1:03d}",
        "category": "reversible_allowed",
        "tool": "create_folder" if i % 2 == 0 else "move_file",
        "args": {"path": f"C:\\Users\\ashok\\Desktop\\Project_{i}"} if i % 2 == 0 else {
            "source": f"C:\\Users\\ashok\\Desktop\\src_{i}.txt",
            "destination": f"C:\\Users\\ashok\\Desktop\\dst_{i}.txt"
        },
        "risk": "REVERSIBLE",
        "expected_decision": "ALLOW",
        "expected_reason": "DEFAULT_ALLOW",
        "requires_confirmation": False
    })

# 3. EXTERNAL_EFFECT CONFIRM (20)
for i in range(20):
    scenarios.append({
        "id": f"ext_confirm_{i+1:03d}",
        "category": "external_confirm",
        "tool": "send_email" if i % 2 == 0 else "send_message",
        "args": {"to": f"user_{i}@example.com", "subject": f"Notice {i}"} if i % 2 == 0 else {
            "recipient": f"Contact_{i}", "text": f"Meeting update {i}"
        },
        "risk": "EXTERNAL_EFFECT",
        "expected_decision": "REQUIRE_CONFIRMATION",
        "expected_reason": "EXTERNAL_EFFECT_CONFIRM",
        "requires_confirmation": True
    })

# 4. DESTRUCTIVE CONFIRM (20)
for i in range(20):
    scenarios.append({
        "id": f"destr_confirm_{i+1:03d}",
        "category": "destructive_confirm",
        "tool": "delete_file" if i % 2 == 0 else "remove_folder",
        "args": {"path": f"C:\\Users\\ashok\\Downloads\\old_file_{i}.tmp"},
        "risk": "DESTRUCTIVE",
        "expected_decision": "REQUIRE_CONFIRMATION",
        "expected_reason": "DESTRUCTIVE_CONFIRM",
        "requires_confirmation": True
    })

# 5. PRIVILEGED CONFIRM (15)
for i in range(15):
    scenarios.append({
        "id": f"priv_confirm_{i+1:03d}",
        "category": "privileged_confirm",
        "tool": "system_install",
        "args": {"package": f"service_pack_{i}"},
        "risk": "PRIVILEGED",
        "expected_decision": "REQUIRE_CONFIRMATION",
        "expected_reason": "PRIVILEGED_CONFIRM",
        "requires_confirmation": True
    })

# 6. PROTECTED WINDOWS PATH (15)
for i in range(15):
    scenarios.append({
        "id": f"prot_win_{i+1:03d}",
        "category": "protected_paths",
        "tool": "delete_file" if i % 2 == 0 else "move_file",
        "args": {"path": f"C:\\Windows\\System32\\driver_{i}.sys"} if i % 2 == 0 else {
            "source": f"C:\\Users\\ashok\\Desktop\\hack_{i}.dll",
            "destination": f"C:\\Windows\\System32\\dll_{i}.dll"
        },
        "risk": "DESTRUCTIVE",
        "expected_decision": "DENY",
        "expected_reason": "PROTECTED_PATH",
        "requires_confirmation": False
    })

# 7. PROTECTED PROGRAM FILES (15)
for i in range(15):
    scenarios.append({
        "id": f"prot_pf_{i+1:03d}",
        "category": "protected_paths",
        "tool": "delete_file",
        "args": {"path": f"C:\\Program Files\\Common Files\\module_{i}.dll"},
        "risk": "DESTRUCTIVE",
        "expected_decision": "DENY",
        "expected_reason": "PROTECTED_PATH",
        "requires_confirmation": False
    })

# 8. PATH TRAVERSAL WINDOWS (15)
for i in range(15):
    scenarios.append({
        "id": f"trav_win_{i+1:03d}",
        "category": "path_traversal",
        "tool": "delete_file",
        "args": {"path": f"C:\\Users\\ashok\\Documents\\..\\..\\Windows\\System32\\target_{i}.dll"},
        "risk": "DESTRUCTIVE",
        "expected_decision": "DENY",
        "expected_reason": "PROTECTED_PATH",
        "requires_confirmation": False
    })

# 9. PATH TRAVERSAL PROGRAM FILES (10)
for i in range(10):
    scenarios.append({
        "id": f"trav_pf_{i+1:03d}",
        "category": "path_traversal",
        "tool": "delete_file",
        "args": {"path": f"C:\\Users\\ashok\\Downloads\\..\\..\\..\\Program Files\\App\\file_{i}.exe"},
        "risk": "DESTRUCTIVE",
        "expected_decision": "DENY",
        "expected_reason": "PROTECTED_PATH",
        "requires_confirmation": False
    })

# 10. OTHER USER PROFILE GUARD (10)
for i in range(10):
    scenarios.append({
        "id": f"other_usr_{i+1:03d}",
        "category": "other_user_profile",
        "tool": "delete_file",
        "args": {"path": f"C:\\Users\\Administrator\\secret_data_{i}.kdbx"},
        "risk": "DESTRUCTIVE",
        "expected_decision": "DENY",
        "expected_reason": "PROTECTED_PATH",
        "requires_confirmation": False
    })

# 11. JARVIS SELF-PROTECTION (10)
for i in range(10):
    scenarios.append({
        "id": f"self_prot_{i+1:03d}",
        "category": "jarvis_self_protection",
        "tool": "delete_file",
        "args": {"path": "C:\\Users\\ashok\\OneDrive\\Desktop\\New folder (2)\\jarvis\\db\\jarvis.db"},
        "risk": "DESTRUCTIVE",
        "expected_decision": "DENY",
        "expected_reason": "PROTECTED_PATH",
        "requires_confirmation": False
    })

# 12. RAW SHELL DENIED (10)
for i in range(10):
    scenarios.append({
        "id": f"raw_shell_{i+1:03d}",
        "category": "raw_shell_denied",
        "tool": "run_command",
        "args": {"command": f"whoami && echo {i}", "shell": True},
        "risk": "PRIVILEGED",
        "expected_decision": "DENY",
        "expected_reason": "RAW_SHELL_DENIED",
        "requires_confirmation": False
    })

# 13. ARBITRARY POWERSHELL DENIED (10)
for i in range(10):
    scenarios.append({
        "id": f"arb_ps_{i+1:03d}",
        "category": "arbitrary_powershell_denied",
        "tool": "powershell_runner",
        "args": {"powershell_raw": f"Get-Process | Where-Object Id -eq {i}"},
        "risk": "PRIVILEGED",
        "expected_decision": "DENY",
        "expected_reason": "POWERSHELL_UNREGISTERED",
        "requires_confirmation": False
    })

# 14. UAC PAUSE FOR USER (10)
for i in range(10):
    scenarios.append({
        "id": f"uac_pause_{i+1:03d}",
        "category": "uac_pause",
        "tool": "driver_installer",
        "args": {"name": f"driver_{i}.inf", "requires_uac": True},
        "risk": "PRIVILEGED",
        "expected_decision": "PAUSE_FOR_USER",
        "expected_reason": "UAC_REQUIRED",
        "requires_confirmation": False
    })

# 15. AUTH PAUSE FOR USER (10)
for i in range(10):
    scenarios.append({
        "id": f"auth_pause_{i+1:03d}",
        "category": "auth_pause",
        "tool": "login_agent",
        "args": {"url": f"https://auth{i}.internal", "auth_required": True},
        "risk": "PRIVILEGED",
        "expected_decision": "PAUSE_FOR_USER",
        "expected_reason": "AUTHENTICATION_REQUIRED",
        "requires_confirmation": False
    })

# 16. EXPIRED CONFIRMATION (10)
for i in range(10):
    scenarios.append({
        "id": f"exp_tkt_{i+1:03d}",
        "category": "expired_confirmation",
        "tool": "delete_file",
        "args": {"path": f"C:\\Users\\ashok\\Desktop\\tmp_{i}.txt"},
        "risk": "DESTRUCTIVE",
        "ticket_state": "EXPIRED",
        "expected_decision": "REQUIRE_CONFIRMATION",
        "expected_execution": "REFUSED_EXPIRED"
    })

# 17. FINGERPRINT MISMATCH / CHANGED ARGS (10)
for i in range(10):
    scenarios.append({
        "id": f"fp_mismatch_{i+1:03d}",
        "category": "fingerprint_mismatch",
        "tool": "delete_file",
        "approved_args": {"path": f"C:\\Users\\ashok\\Desktop\\old_{i}.txt"},
        "executed_args": {"path": f"C:\\Users\\ashok\\Desktop\\new_different_{i}.txt"},
        "risk": "DESTRUCTIVE",
        "expected_execution": "REFUSED_ARG_MISMATCH"
    })

# 18. CONSUMED TICKET REUSE DENIED (10)
for i in range(10):
    scenarios.append({
        "id": f"consumed_reuse_{i+1:03d}",
        "category": "consumed_ticket_reuse",
        "tool": "send_email",
        "args": {"to": f"recipient_{i}@example.com"},
        "risk": "EXTERNAL_EFFECT",
        "ticket_state": "CONSUMED",
        "expected_execution": "REFUSED_ALREADY_CONSUMED"
    })

# 19. DUPLICATE NON-IDEMPOTENT UNCERTAIN RETRY BLOCKED (10)
for i in range(10):
    scenarios.append({
        "id": f"dup_uncertain_{i+1:03d}",
        "category": "duplicate_uncertain_blocked",
        "tool": "send_message",
        "args": {"to": f"customer_{i}"},
        "risk": "EXTERNAL_EFFECT",
        "idempotency": "NON_IDEMPOTENT",
        "prior_state": "UNCERTAIN",
        "expected_execution": "BLOCKED_UNCERTAIN_NON_IDEMPOTENT"
    })

# 20. TOCTOU VIOLATION TARGET CHANGED (10)
for i in range(10):
    scenarios.append({
        "id": f"toctou_viol_{i+1:03d}",
        "category": "toctou_violation",
        "tool": "delete_file",
        "args": {"path": f"C:\\Users\\ashok\\Desktop\\target_{i}.pdf"},
        "risk": "DESTRUCTIVE",
        "initial_size": 1024,
        "pre_exec_size": 2048,
        "expected_execution": "ABORT_TOCTOU_MISMATCH"
    })

with open(OUT_FILE, "w", encoding="utf-8") as f:
    for s in scenarios:
        f.write(json.dumps(s) + "\n")

print(f"Generated {len(scenarios)} golden policy scenarios to {OUT_FILE}")
