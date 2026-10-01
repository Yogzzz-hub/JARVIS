"""Documented corrections to frozen Phase-500 expectations (cases.py / build.py stay byte-identical, see FROZEN.sha256).

A correction is allowed only when the frozen expectation itself was wrong - the template named a tool that was planned
as NEW although an existing tool already does exactly what was asked. A correction never accepts a different behaviour
because the router happens to produce it. The runner applies these by template, prints how many cases they touched and
marks each one ``corrected`` in its JSON output.
"""
from __future__ import annotations

# template text (exactly as in cases.py) -> (corrected expect, corrected slots or None to keep, reason)
CORRECTIONS: dict[str, tuple[str, dict | None, str]] = {
    "set my phone brightness to {n} percent": (
        "phone_op|android_quick_action", None,
        "android_quick_action already sets an exact phone brightness (action=brightness, value 0-100) over ADB; the "
        "template expected only the planned phone_op key, and its slot names differ ('value' vs 'percent')."),
    "dim my phone to {n}%": (
        "phone_op|android_quick_action", None,
        "same as above: exact phone brightness is an existing android_quick_action."),
}


def apply(case: dict) -> dict:
    fix = CORRECTIONS.get(case.get("template", ""))
    if not fix:
        return case
    expect, slots, _why = fix
    return {**case, "expect": expect, "slots": case["slots"] if slots is None else slots, "corrected": True}
