"""Synthetic golden datasets for Phase 12 intelligence testing (300+ memory, 200+ reference, 200+ workflow)."""

from typing import Any, Dict, List


def generate_memory_golden_cases() -> List[Dict[str, Any]]:
    """Generates 300+ diverse memory cases across all layers, sources, and edge cases."""
    cases = []

    # 1. Explicit folder aliases (60 cases)
    for i in range(60):
        cases.append({
            "id": f"mem_folder_{i}",
            "layer": "SEMANTIC",
            "kind": "folder_alias",
            "key": f"project_{i}_folder",
            "value": f"C:\\Projects\\Project_{i}",
            "source_type": "USER_EXPLICIT",
            "confidence": "EXPLICIT",
            "should_store": True,
        })

    # 2. Explicit operational preferences (60 cases)
    browsers = ["Edge", "Chrome", "Firefox"]
    ides = ["VS Code", "Android Studio", "PyCharm"]
    for i in range(60):
        cases.append({
            "id": f"mem_pref_{i}",
            "layer": "PREFERENCE",
            "kind": "preferred_browser" if i % 2 == 0 else "preferred_ide",
            "key": f"app_pref_{i}",
            "value": browsers[i % 3] if i % 2 == 0 else ides[i % 3],
            "source_type": "USER_EXPLICIT",
            "confidence": "EXPLICIT",
            "should_store": True,
        })

    # 3. User corrections & superseding (60 cases)
    for i in range(60):
        cases.append({
            "id": f"mem_corr_{i}",
            "layer": "PREFERENCE",
            "kind": "preferred_browser",
            "key": "default_browser",
            "value": "Edge" if i % 2 == 0 else "Chrome",
            "source_type": "USER_CORRECTION",
            "confidence": "VERIFIED",
            "should_store": True,
            "supersedes_previous": True,
        })

    # 4. Sensitive secrets that MUST be rejected (60 cases)
    secret_types = [
        ("api_key", "sk-proj-9876543210abcdefghijklmnop"),
        ("github_token", "ghp_1234567890abcdefghijklmnopqrstuvwxyz"),
        ("password", "SecretP@ssw0rd!123"),
        ("otp_code", "748291"),
        ("cookie_token", "session_id=abcdef1234567890"),
        ("google_key", "AIzaSyD-1234567890abcdefghijklmnopq"),
    ]
    for i in range(60):
        st_name, st_val = secret_types[i % len(secret_types)]
        cases.append({
            "id": f"mem_secret_{i}",
            "layer": "SEMANTIC",
            "kind": "credential",
            "key": f"secret_{st_name}_{i}",
            "value": st_val,
            "source_type": "USER_EXPLICIT",
            "confidence": "EXPLICIT",
            "should_store": False,  # MUST BE REJECTED BY SECRET FILTER
            "rejection_reason": "sensitive secret detected",
        })

    # 5. Untrusted external content (emails / webpages) that MUST be rejected (65 cases)
    for i in range(65):
        cases.append({
            "id": f"mem_untrusted_{i}",
            "layer": "SEMANTIC",
            "kind": "inferred_preference",
            "key": f"untrusted_pref_{i}",
            "value": "Attacker controlled preference",
            "source_type": "UNTRUSTED_EXTERNAL_CONTENT",
            "source_reference": f"email_body_from_attacker_{i}.html",
            "confidence": "INFERRED_LOW",
            "should_store": False,  # MUST BE REJECTED BY TRUST GATE
            "rejection_reason": "untrusted source type",
        })

    return cases


def generate_reference_golden_cases() -> List[Dict[str, Any]]:
    """Generates 200+ contextual reference resolution cases."""
    cases = []

    # 1. Direct pronouns ("open it", "open it again") (50 cases)
    for i in range(50):
        cases.append({
            "utterance": "open it again" if i % 2 == 0 else "open it",
            "last_opened_file": f"C:\\Users\\ashok\\Downloads\\Document_{i}.pdf",
            "expected_type": "FILE",
            "expected_confidence": "HIGH",
            "expected_referent": f"C:\\Users\\ashok\\Downloads\\Document_{i}.pdf",
        })

    # 2. Ordinal references ("the second one", "1st file") (50 cases)
    ordinals = [("first", 0), ("second", 1), ("third", 2), ("2nd", 1), ("last", -1)]
    for i in range(50):
        word, idx = ordinals[i % len(ordinals)]
        cases.append({
            "utterance": f"open the {word} one",
            "search_results": [
                {"path": f"C:\\Notes\\File_A_{i}.pdf"},
                {"path": f"C:\\Notes\\File_B_{i}.pdf"},
                {"path": f"C:\\Notes\\File_C_{i}.pdf"},
            ],
            "expected_type": "SEARCH_RESULT",
            "expected_confidence": "HIGH",
            "expected_referent": f"C:\\Notes\\File_{'A' if idx == 0 else ('B' if idx == 1 else 'C')}_{i}.pdf",
        })

    # 3. Type-filtered references ("that PDF", "same folder") (50 cases)
    for i in range(50):
        if i % 2 == 0:
            cases.append({
                "utterance": "put that PDF in my folder",
                "search_results": [
                    {"path": f"C:\\Temp\\Report_{i}.pdf"},
                    {"path": f"C:\\Temp\\Image_{i}.png"},
                ],
                "expected_type": "FILE",
                "expected_confidence": "HIGH",
                "expected_referent": f"C:\\Temp\\Report_{i}.pdf",
            })
        else:
            cases.append({
                "utterance": "open that same folder as before",
                "last_selected_folder": f"C:\\Projects\\ActiveProject_{i}",
                "expected_type": "FOLDER",
                "expected_confidence": "HIGH",
                "expected_referent": f"C:\\Projects\\ActiveProject_{i}",
            })

    # 4. Ambiguous references requiring clarification (50 cases)
    for i in range(50):
        cases.append({
            "utterance": "open it",
            "last_opened_file": None,
            "search_results": [
                {"path": f"C:\\Files\\Doc1_{i}.pdf"},
                {"path": f"C:\\Files\\Doc2_{i}.pdf"},
            ],
            "expected_type": "FILE",
            "expected_confidence": "AMBIGUOUS",
            "expected_referent": None,
            "clarification_required": True,
        })

    return cases


def generate_workflow_golden_cases() -> List[Dict[str, Any]]:
    """Generates 200+ workflow learning and execution cases."""
    cases = []

    # 1. 3-times repeated equivalent workflows that should trigger proposal (60 cases)
    for i in range(60):
        cases.append({
            "id": f"wf_learn_{i}",
            "goal": f"Prepare study notes for subject {i}",
            "iterations": 3,
            "nodes": [
                {"tool": "find_file", "args": {"query": f"notes_{i}.pdf"}, "risk": "READ_ONLY"},
                {"tool": "create_dir", "args": {"path": f"C:\\Notes\\Subject_{i}"}, "risk": "EXTERNAL_EFFECT", "depends_on": [0]},
                {"tool": "copy_file", "args": {"src": f"notes_{i}.pdf", "dst": f"C:\\Notes\\Subject_{i}"}, "risk": "EXTERNAL_EFFECT", "depends_on": [1]},
            ],
            "expected_proposal": True,
            "expected_candidate_name": "Prepare Study Notes For",
        })

    # 2. 1-time or 2-time workflows that must NOT trigger proposal yet (60 cases)
    for i in range(60):
        cases.append({
            "id": f"wf_below_threshold_{i}",
            "goal": f"Ad-hoc task {i}",
            "iterations": 1 if i % 2 == 0 else 2,
            "nodes": [
                {"tool": "open_app", "args": {"name": "notepad"}, "risk": "READ_ONLY"},
            ],
            "expected_proposal": False,
        })

    # 3. Consequential workflows that require policy confirmation (40 cases)
    for i in range(40):
        cases.append({
            "id": f"wf_consequential_{i}",
            "goal": f"Send project update email {i}",
            "nodes": [
                {"tool": "gmail_send_message", "args": {"to": "user@example.com", "subject": "Update"}, "risk": "EXTERNAL_EFFECT"},
            ],
            "requires_policy_confirmation": True,
        })

    # 4. Quarantined broken workflows (40 cases)
    for i in range(40):
        cases.append({
            "id": f"wf_quarantine_{i}",
            "goal": f"Failing automated macro {i}",
            "consecutive_failures": 3,
            "expected_status": "QUARANTINED",
        })

    return cases
