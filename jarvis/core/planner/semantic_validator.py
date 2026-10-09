"""Semantic plan validation: a structurally valid TaskGraph can still be the wrong plan.

``GraphValidator`` proves a graph is well formed (tools exist, required arguments are present, types and dependencies
fit, no cycles). It cannot tell whether the graph does what the owner asked. This module checks the graph against the
request itself - the same constraint, policy and destructive-scope models the router uses - so the planner can never
compensate for, or reintroduce, something the router would have refused:

* NEGATED_ACTION      a step performs an effect the owner said not to ("don't send it", "don't pay")
* EXCLUDED_TARGET     a step is aimed at someone / something the owner excluded ("everyone except Arun")
* REJECTED_VALUE      a step uses the alternative the owner rejected ("PDF, not the screenshot")
* POLICY_VIOLATION    the request is a must-never class (payment, secrets, third-party device ...)
* UNREQUESTED_ACTION  a destructive or outward-facing step with no verb in the request that asks for it
* DESTRUCTIVE_TARGET  a literal destructive target that the scope guard would refuse (a whole user folder, a drive)
"""
from __future__ import annotations

import re
from typing import Iterable

from jarvis.core.planner.validator import GraphValidationError

# the effect each tool has and the words that can ask for it; a step with such a tool needs one of these in the request
_EVIDENCE: dict[str, re.Pattern] = {
    "destroy": re.compile(r"\b(?:delete|remove|erase|trash|bin|discard|throw|toss|dump|junk|get\s+rid|clear|empty|uninstall|wipe|"
                          r"clean\s*up|purge|scrap|rename|batch)\b", re.I),
    "message": re.compile(r"\b(?:send|message|msg|text|tell|reply|respond|forward|share|whatsapp|mail|email|ping|inform|notify|"
                          r"let\s+\w+\s+know|ask|write|dm|draft|compose|post|deliver|drop)\b", re.I),
    "power": re.compile(r"\b(?:shut|shutdown|restart|reboot|lock|sleep|hibernate|log\s*off|sign\s*out|power|turn\s+off)\b", re.I),
    "install": re.compile(r"\b(?:install|download|get|set\s*up|add|grab)\b", re.I),
    "close": re.compile(r"\b(?:close|quit|exit|kill|stop|end|terminate|shut)\b", re.I),
}
_TOOL_EFFECT = {
    "delete_file": "destroy", "uninstall_software": "destroy", "empty_recycle_bin": "destroy", "batch_rename": "destroy",
    "send_whatsapp_message": "message", "send_whatsapp_bulk": "message", "reply_whatsapp_message": "message",
    "reply_whatsapp_all": "message", "gmail_create_draft": "message", "localsend_text": "message", "localsend_file": "message",
    "system_power_control": "power", "install_software": "install", "close_app": "close",
}
_VALUE_KEYS = ("name", "app", "target", "path", "source", "file", "recipient", "contact", "to", "query", "title", "text", "message")
_RECIPIENT_KEYS = ("recipient", "contact", "to", "name", "target")


def _args_text(args: dict) -> str:
    return " ".join(str(v) for k, v in (args or {}).items() if k in _VALUE_KEYS and isinstance(v, (str, int, float))).lower()


def semantic_errors(graph, request_text: str, consequential: Iterable[str] = ()) -> list[GraphValidationError]:
    """Errors for a graph that is well formed but does not match ``request_text``. Empty list = the plan fits the request."""
    from jarvis.core.router.router import SmartRouter
    from jarvis.core.semantics import policy
    from jarvis.core.semantics.constraints import contrast, extract_exclusions, prohibitions, trailing_prohibition

    text = " ".join((request_text or "").split())
    errors: list[GraphValidationError] = []
    nodes = list(getattr(graph, "nodes", []) or [])
    if not nodes or not text:
        return errors
    tools = [n.tool for n in nodes]

    # --- policy: the planner is not a way around a refusal
    verdict = policy.check(tools, text, consequential or SmartRouter._CONSEQUENTIAL_EFFECTS)
    if verdict and verdict["kind"] == "refuse":
        errors.append(GraphValidationError(code="POLICY_VIOLATION", message=f"The request is blocked by policy ({verdict['reason']}); "
                                           f"no plan may act on it"))
        return errors

    # --- negative constraints: prohibited effects, excluded targets, rejected alternatives
    _, prohibited = prohibitions(text)
    if not prohibited:
        _, prohibited = trailing_prohibition(text)
    positive_ex, excluded = extract_exclusions(text)
    _, rejected = contrast(text)
    for p in prohibited:
        verb = (re.match(r"[a-z]+", p.lower()) or [""])[0]
        effect = SmartRouter._PROHIBITED_EFFECT.get(verb)
        obj = re.sub(r"^\S+\s+(?:(?:the|my|a|an)\s+)?", "", p.lower(), count=1).strip()
        generic = not obj or re.match(r"(?:it|that|this|them|anything|anyone|anybody|everyone|everybody|everything|any\s+\w+|yet|now)\b", obj)
        for n in nodes:
            if effect and n.tool in SmartRouter._EFFECT_TOOLS.get(effect, set()) and (generic or obj in _args_text(n.args)):
                errors.append(GraphValidationError(code="NEGATED_ACTION", node_id=n.id, field="tool",
                                                   message=f"The owner said not to {p}; step {n.id} ({n.tool}) does it"))
    for n in nodes:
        blob = _args_text(n.args)
        for x in excluded:
            if x.lower() in blob and n.tool in SmartRouter._EFFECT_TOOLS.get("message", set()) | set(_TOOL_EFFECT) \
                    and any(x.lower() in str(n.args.get(k, "")).lower() for k in _RECIPIENT_KEYS):
                errors.append(GraphValidationError(code="EXCLUDED_TARGET", node_id=n.id,
                                                   message=f"'{x}' was excluded by the owner but step {n.id} is aimed at it"))
        for x in rejected:
            if x.lower() in blob:
                errors.append(GraphValidationError(code="REJECTED_VALUE", node_id=n.id,
                                                   message=f"The owner rejected '{x}' but step {n.id} uses it"))

    # --- nothing destructive or outward is introduced without being asked for
    ask_text = positive_ex or text
    for n in nodes:
        effect = _TOOL_EFFECT.get(n.tool)
        if effect and not _EVIDENCE[effect].search(ask_text):
            errors.append(GraphValidationError(code="UNREQUESTED_ACTION", node_id=n.id, field="tool",
                                               message=f"Step {n.id} ({n.tool}) has effect '{effect}', which the request never asks for"))

    # --- literal destructive targets pass the same scope guard the executor applies
    from jarvis.security.destructive import DESTRUCTIVE_FILE_TOOLS, check_destructive_target
    for n in nodes:
        if n.tool in DESTRUCTIVE_FILE_TOOLS and DESTRUCTIVE_FILE_TOOLS[n.tool] in (n.args or {}):
            try:
                chk = check_destructive_target(n.tool, dict(n.args))
            except Exception:
                chk = None
            if chk is not None and chk.status == "BLOCKED_BY_POLICY":
                errors.append(GraphValidationError(code="DESTRUCTIVE_TARGET", node_id=n.id, field=DESTRUCTIVE_FILE_TOOLS[n.tool],
                                                   message=chk.message))
    return errors
