"""Universal Operator: routing of the semantic scenarios and route -> tool -> observed effect on the fake world.

The full scenario run (all surface forms + holdout) is `python -m tests.operator.runner [--holdout]`; this keeps a
fast, deterministic slice in the unit suite and pins the zero-tolerance rules (negation, secrets, wrong tool)."""
from __future__ import annotations

import asyncio
import random

import pytest

from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter
from tests.operator.runner import judge
from tests.operator.scenarios import SCENARIOS
from tests.operator.surface import dev_forms, negated


def _route(text: str):
    return asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route(text))


def test_scenario_count_and_families():
    fams = {s.family for s in SCENARIOS}
    assert len(SCENARIOS) >= 500
    assert {"desktop", "text", "ui", "browser", "media", "clipboard", "files", "ide", "android", "cross", "system",
            "workflow"} <= fams


@pytest.mark.parametrize("sc", SCENARIOS[::4], ids=lambda s: s.id)
def test_canonical_wording_routes(sc):
    d = _route(sc.seeds[0])
    ok, why = judge(sc, d)
    assert ok, f"{sc.seeds[0]!r}: {why}"


@pytest.mark.parametrize("sc", [s for s in SCENARIOS[1::6] if not s.intent.startswith("*")], ids=lambda s: s.id)
def test_negated_wording_never_runs(sc):
    d = _route(negated(sc.seeds[0]))
    lane = getattr(d.lane, "value", d.lane)
    assert lane in ("REJECT", "CLARIFY") or d.intent in (None, "clarify", "standing_rule"), (sc.seeds[0], lane, d.intent)


@pytest.mark.parametrize("text", ["type my password in the password field", "enter the otp in the code box",
                                  "put my pin in the pin field", "type 1234 in the cvv box"])
def test_secrets_are_never_typed(text):
    d = _route(text)
    assert getattr(d.lane, "value", d.lane) in ("CLARIFY", "REJECT", "LANE_2") and d.intent != "ui_op"


@pytest.mark.parametrize("text,bad", [("delete the last three words", "delete_file"), ("delete the last sentence", "delete_file"),
                                      ("click the second button", "delete_file"), ("paste that screenshot in antigravity", "take_screenshot"),
                                      ("open the third result", "open_file"), ("rewind 30 seconds", "set_reminder"),
                                      ("discard the suggestions in vs code", None)])
def test_former_misroutes_are_fixed(text, bad):
    d = _route(text)
    assert d.intent != bad and (d.intent or "").endswith("_op"), (text, d.intent)


def test_surface_forms_of_a_sample_hold():
    rng = random.Random(3)
    sample = [s for s in SCENARIOS if s.intent.endswith("_op")][::9]
    bad = []
    for sc in sample:
        for kind, text in dev_forms(sc.seeds[0], rng):
            ok, why = judge(sc, _route(text))
            if not ok:
                bad.append((kind, text, why))
    assert len(bad) <= max(2, len(sample) // 25), bad


# ------------------------------------------------------------------------------------------------- end to end
@pytest.fixture
def world(tmp_path):
    from jarvis.core.operator.platform import FakeDesktop, set_desktop
    from jarvis.core.operator.resources import OperatorResources, set_resources
    from jarvis.core.operator.windows import WindowTracker, set_window_tracker
    from jarvis.tools.system import operator_tools
    d = FakeDesktop()
    set_desktop(d)
    tr = WindowTracker(d)
    set_window_tracker(tr)
    set_resources(OperatorResources())
    tools = {t.definition.name: t for t in operator_tools.create_operator_tools()}
    h = {"editor": d.open("notepad.exe", "notes.txt - Notepad", editable=True, text="Meet on Tuesday at noon. Bring snacks"),
         "browser": d.open("chrome.exe", "Docs - Google Chrome"),
         "jarvis": d.open("python.exe", "JARVIS EDGE")}
    for k in ("editor", "browser", "jarvis"):
        d.focus(h[k])
        tr.observe()
    yield d, tr, tools, h
    set_desktop(None)
    set_window_tracker(None)
    set_resources(None)


def _run(tools, decision):
    if decision.subcommands:
        return [_run_one(tools, s.tool, s.arguments) for s in decision.subcommands]
    return [_run_one(tools, decision.intent, decision.slots)]


def _run_one(tools, name, slots):
    tool = tools[name]
    fields = tool.definition.input_model.model_fields
    args = tool.definition.input_model.model_validate({k: v for k, v in slots.items() if k in fields})
    return tool.definition.output_model.model_validate(tool.run(args))


def test_e2e_go_back_to_editor_and_delete_last_word(world):
    d, tr, tools, h = world
    out = _run(tools, _route("go back to my editor and delete the last word"))
    assert all(o.ok for o in out)
    assert d.foreground().hwnd == h["editor"] and d.buffer(h["editor"]).text == "Meet on Tuesday at noon. Bring "


def test_e2e_replace_and_switch_previous(world):
    d, tr, tools, h = world
    _run(tools, _route("go back to notepad"))
    _run(tools, _route("replace tuesday with Wednesday"))
    assert "Wednesday" in d.buffer(h["editor"]).text
    _run(tools, _route("switch to the previous window"))
    assert d.foreground().hwnd == h["browser"]


def test_e2e_side_by_side(world):
    d, tr, tools, h = world
    _run(tools, _route("put chrome and notepad side by side"))
    assert d.window_rect(h["browser"])[2] <= d.window_rect(h["editor"])[0] + 16


def test_e2e_negated_and_secret_requests_touch_nothing(world):
    d, tr, tools, h = world
    before = (d.buffer(h["editor"]).text, list(d.keys), list(d.typed))
    for text in ("don't delete the last word", "type my password in the password field"):
        dec = _route(text)
        assert not (dec.intent or "").endswith("_op")
    assert (d.buffer(h["editor"]).text, d.keys, d.typed) == before
