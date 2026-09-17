from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from jarvis.security.paths import is_protected_path, canonicalize_path
from jarvis.security.policy.models import PolicyDecision, PolicyDecisionType, PolicyReasonCode
from jarvis.tools.base import RiskLevel, ToolDefinition

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "policy.toml"

class PolicyEvaluator:
    """Pre-compiled, ultra-fast deterministic policy evaluator.
    Loads policy.toml once and compiles fast lookup structures to evaluate
    decisions in < 0.25ms p95 without I/O or LLM involvement.
    """

    def __init__(self, policy_path: Path | str | None = None) -> None:
        self.policy_path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
        self._load_and_compile_policy()

    def _load_and_compile_policy(self) -> None:
        if self.policy_path.exists():
            with open(self.policy_path, "rb") as f:
                data = tomllib.load(f)
        else:
            data = {}

        defaults = data.get("defaults", {})
        self.default_rules: dict[RiskLevel, str] = {
            RiskLevel.READ_ONLY: defaults.get("READ_ONLY", "ALLOW"),
            RiskLevel.REVERSIBLE: defaults.get("REVERSIBLE", "ALLOW"),
            RiskLevel.EXTERNAL_EFFECT: defaults.get("EXTERNAL_EFFECT", "CONFIRM"),
            RiskLevel.DESTRUCTIVE: defaults.get("DESTRUCTIVE", "CONFIRM_ALWAYS"),
            RiskLevel.PRIVILEGED: defaults.get("PRIVILEGED", "CONFIRM_ALWAYS"),
        }

        confirmation = data.get("confirmation", {})
        self.confirmation_timeout_s: float = float(confirmation.get("timeout_seconds", 30.0))
        self.single_confirmation_per_graph: bool = bool(confirmation.get("single_confirmation_per_graph", True))

        paths = data.get("paths", {})
        self.protected_roots: list[str] = paths.get("protected_roots", [
            "C:\\Windows",
            "C:\\Program Files",
            "C:\\Program Files (x86)",
        ])
        self.deny_other_user_profiles: bool = bool(paths.get("deny_other_user_profiles", True))

        execution = data.get("execution", {})
        self.allow_raw_shell: bool = bool(execution.get("allow_raw_shell", False))
        self.allow_arbitrary_powershell: bool = bool(execution.get("allow_arbitrary_powershell", False))
        self.allow_uac_automation: bool = bool(execution.get("allow_uac_automation", False))
        self.allow_password_automation: bool = bool(execution.get("allow_password_automation", False))
        self.allow_otp_automation: bool = bool(execution.get("allow_otp_automation", False))
        self.allow_captcha_automation: bool = bool(execution.get("allow_captcha_automation", False))

        # Precompile path keywords for argument scanning
        self.path_keys = frozenset([
            "path", "source", "destination", "dest", "target", "file_path", 
            "folder_path", "directory", "root", "old_path", "new_path"
        ])

    def evaluate_node(
        self,
        tool_def: ToolDefinition | None,
        args: dict[str, Any],
        graph_id: str = "",
        node_id: str = "",
    ) -> PolicyDecision:
        """Evaluates policy for a single task node deterministically in microseconds."""
        t0 = time.perf_counter_ns()

        # 1. Tool existence check
        if tool_def is None:
            eval_ms = (time.perf_counter_ns() - t0) / 1e6
            return PolicyDecision(
                decision=PolicyDecisionType.DENY,
                risk=RiskLevel.PRIVILEGED,
                reason_code=PolicyReasonCode.UNKNOWN_TOOL_RISK,
                rule_id="RULE_UNKNOWN_TOOL",
                constraints={"error": "Tool does not exist in registry"},
                evaluated_ms=eval_ms,
            )

        # 2. Risk classification from trusted ToolDefinition (never LLM)
        risk = tool_def.risk

        # 3. Execution restrictions
        tags = set(tool_def.tags)
        if "uac" in tags or "uac_required" in tags or args.get("requires_uac"):
            eval_ms = (time.perf_counter_ns() - t0) / 1e6
            return PolicyDecision(
                decision=PolicyDecisionType.PAUSE_FOR_USER,
                risk=risk,
                reason_code=PolicyReasonCode.UAC_REQUIRED,
                rule_id="RULE_UAC_GUARD",
                confirmation_scope=f"node:{node_id}",
                constraints={"message": "Windows needs your approval (UAC) to continue."},
                evaluated_ms=eval_ms,
            )

        if "auth_required" in tags or "password_required" in tags or "captcha" in tags or args.get("auth_required") or args.get("password_required"):
            eval_ms = (time.perf_counter_ns() - t0) / 1e6
            return PolicyDecision(
                decision=PolicyDecisionType.PAUSE_FOR_USER,
                risk=risk,
                reason_code=PolicyReasonCode.AUTHENTICATION_REQUIRED,
                rule_id="RULE_AUTH_GUARD",
                confirmation_scope=f"node:{node_id}",
                constraints={"message": "Authentication or credentials required; automation forbidden."},
                evaluated_ms=eval_ms,
            )

        # 4. Raw shell / arbitrary script restrictions
        if not self.allow_raw_shell and (args.get("shell") is True or "raw_shell" in tags):
            eval_ms = (time.perf_counter_ns() - t0) / 1e6
            return PolicyDecision(
                decision=PolicyDecisionType.DENY,
                risk=RiskLevel.PRIVILEGED,
                reason_code=PolicyReasonCode.RAW_SHELL_DENIED,
                rule_id="RULE_NO_RAW_SHELL",
                constraints={"error": "Raw shell execution is forbidden by policy."},
                evaluated_ms=eval_ms,
            )

        if not self.allow_arbitrary_powershell and (args.get("powershell_raw") or "arbitrary_ps" in tags):
            eval_ms = (time.perf_counter_ns() - t0) / 1e6
            return PolicyDecision(
                decision=PolicyDecisionType.DENY,
                risk=RiskLevel.PRIVILEGED,
                reason_code=PolicyReasonCode.POWERSHELL_UNREGISTERED,
                rule_id="RULE_POWERSHELL_TEMPLATE_ONLY",
                constraints={"error": "Arbitrary PowerShell commands are forbidden. Use registered templates."},
                evaluated_ms=eval_ms,
            )

        # 5. Path argument validation (Protected paths, Traversal, Self-protection)
        # Read-only tools (like search/list) are allowed to inspect paths, but mutating tools are barred.
        if risk != RiskLevel.READ_ONLY:
            for k, v in args.items():
                if k.lower() in self.path_keys and isinstance(v, (str, Path)):
                    protected, reason = is_protected_path(
                        v,
                        protected_roots=self.protected_roots,
                        deny_other_users=self.deny_other_user_profiles,
                        protect_jarvis_internals=True,
                    )
                    if protected:
                        eval_ms = (time.perf_counter_ns() - t0) / 1e6
                        return PolicyDecision(
                            decision=PolicyDecisionType.DENY,
                            risk=risk,
                            reason_code=PolicyReasonCode.PROTECTED_PATH,
                            rule_id="RULE_PROTECTED_PATH_GUARD",
                            confirmation_scope=f"node:{node_id}",
                            constraints={"path": str(v), "reason": reason},
                            evaluated_ms=eval_ms,
                        )

        # 6. Apply default risk policy
        rule_action = self.default_rules.get(risk, "CONFIRM")
        eval_ms = (time.perf_counter_ns() - t0) / 1e6

        if rule_action == "ALLOW" and not tool_def.requires_confirmation:
            return PolicyDecision(
                decision=PolicyDecisionType.ALLOW,
                risk=risk,
                reason_code=PolicyReasonCode.DEFAULT_ALLOW,
                rule_id=f"RULE_ALLOW_{risk.name}",
                evaluated_ms=eval_ms,
            )

        # Requires confirmation based on risk
        reason_code_map = {
            RiskLevel.EXTERNAL_EFFECT: PolicyReasonCode.EXTERNAL_EFFECT_CONFIRM,
            RiskLevel.DESTRUCTIVE: PolicyReasonCode.DESTRUCTIVE_CONFIRM,
            RiskLevel.PRIVILEGED: PolicyReasonCode.PRIVILEGED_CONFIRM,
            RiskLevel.REVERSIBLE: PolicyReasonCode.EXTERNAL_EFFECT_CONFIRM,
            RiskLevel.READ_ONLY: PolicyReasonCode.DEFAULT_ALLOW,
        }

        return PolicyDecision(
            decision=PolicyDecisionType.REQUIRE_CONFIRMATION,
            risk=risk,
            reason_code=reason_code_map.get(risk, PolicyReasonCode.EXTERNAL_EFFECT_CONFIRM),
            rule_id=f"RULE_CONFIRM_{risk.name}",
            confirmation_scope=f"node:{node_id}",
            constraints={"timeout_seconds": self.confirmation_timeout_s},
            evaluated_ms=eval_ms,
        )
