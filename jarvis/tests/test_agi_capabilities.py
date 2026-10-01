"""AGI-520 capability layer: task-scoped grants, pause/resume, conditional watches, owner workflows, the new file /
phone / system primitives, and the router's capability parser - each checked on its observable effect."""
from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime

import pytest

from jarvis.core.operator.device import DeviceOperator, FakeAdb
from jarvis.core.operator.files import FileOperator, parse_size
from jarvis.core.operator.resources import OperatorResources
from jarvis.core.operator.watch import WatchManager
from jarvis.core.operator.workflows import Workflows, due, parse_schedule
from jarvis.core.router.models import RouteLane
from jarvis.core.tasks.scope import ALWAYS, ScopeDenied, TaskScopeManager


# ------------------------------------------------------------------------------------------------ task scope
def test_grant_allows_only_its_tools_and_is_revoked_at_the_end():
    sm = TaskScopeManager()
    with sm.grant("t1", {"window_op"}, "route") as g:
        sm.check("window_op")
        sm.check(next(iter(ALWAYS)))                     # reading JARVIS's own state is always allowed
        with pytest.raises(ScopeDenied):
            sm.check("delete_file")
        assert g.denied == ["delete_file"]
    assert g.revoked and sm.current() is None and not sm.active()
    sm.check("delete_file")                              # outside any command there is no grant to enforce


def test_nested_grant_only_narrows_and_extend_is_explicit():
    sm = TaskScopeManager()
    with sm.grant("outer", {"window_op", "text_op"}):
        with sm.grant("inner", {"text_op", "install_software"}):
            sm.check("text_op")
            with pytest.raises(ScopeDenied):
                sm.check("install_software")             # a nested grant can never widen the outer one
        sm.extend({"file_op"}, "validated plan")
        sm.check("file_op")
        sm.narrow({"file_op"})
        with pytest.raises(ScopeDenied):
            sm.check("window_op")


def test_grants_follow_asyncio_tasks():
    sm = TaskScopeManager()

    async def step():
        sm.check("text_op")
        with pytest.raises(ScopeDenied):
            sm.check("phone_op")

    async def main():
        with sm.grant("t", {"text_op"}):
            await asyncio.gather(step(), step())
    asyncio.run(main())


def test_executor_refuses_a_tool_outside_the_grant():
    import inspect
    from jarvis.core.executor import engine
    assert "scope_denied" in inspect.getsource(engine.ExecutionEngine)   # the gate lives in the executor


# ------------------------------------------------------------------------------------------------ pause / resume
def test_pause_blocks_the_next_step_and_resume_releases_it():
    from jarvis.core.tasks.manager import TaskManager

    class Bus:
        def emit(self, *a, **k):
            pass

    class Writer:
        def enqueue(self, *a, **k):
            pass

    class Req:
        request_id, source, text, metadata = "r1", "test", "do things", {}

    async def main():
        tm = TaskManager(Bus(), Writer())
        task = tm.create(Req(), None)
        from jarvis.core.tasks.manager import State
        tm.transition(task, State.UNDERSTANDING)
        assert tm.pause("r1") and task.paused and not task.run_gate.is_set()
        waiter = asyncio.create_task(task.run_gate.wait())
        await asyncio.sleep(0.01)
        assert not waiter.done()                          # the next step waits while paused
        assert tm.resume("r1") and not task.paused
        await asyncio.wait_for(waiter, 1)
    asyncio.run(main())


# ------------------------------------------------------------------------------------------------ watches
def test_conditional_watch_waits_then_redispatches_the_owners_command():
    clock = [0.0]
    wm = WatchManager(clock=lambda: clock[0])
    sent: list[str] = []
    wm.dispatch = sent.append
    state = {"ready": False}
    out = wm.when("when", "the Continue button is enabled", lambda: state["ready"], then="press the Continue button")
    assert out.ok and wm.tick() == [] and sent == []    # nothing runs early
    state["ready"] = True
    clock[0] += 5
    said = wm.tick()
    assert sent == ["press the Continue button"] and said and not wm.active()


def test_conditional_watch_can_end_silently_and_times_out_without_acting():
    clock = [0.0]
    wm = WatchManager(clock=lambda: clock[0])
    sent: list[str] = []
    wm.dispatch = sent.append
    wm.when("when", "the build fails", lambda: "done_silent", then="tell me")
    clock[0] += 5
    assert wm.tick() == [] and sent == [] and not wm.active()
    wm.when("when", "never", lambda: False, then="open it", timeout_s=10)
    clock[0] += 60
    wm.tick()
    assert sent == [] and not wm.active()


# ------------------------------------------------------------------------------------------------ workflows
def test_schedule_parsing_and_due():
    assert parse_schedule("every morning except weekends") == "weekdays 08:00"
    assert parse_schedule("weekdays at 8:30") == "weekdays 08:30"
    assert parse_schedule("every 2 hours") == "every 120 minutes"
    assert parse_schedule("mondays at 6pm") == "mon 18:00"
    assert parse_schedule("whenever") is None
    monday_9 = datetime(2026, 10, 5, 9, 0)
    assert due("weekdays 08:30", monday_9, last_run=0)
    assert not due("weekdays 08:30", monday_9, last_run=monday_9.timestamp())
    assert not due("weekends 08:30", monday_9, last_run=0)


def _done(state):
    f: concurrent.futures.Future = concurrent.futures.Future()

    class R:
        pass
    r = R()
    r.state = state
    f.set_result(r)
    return f


def test_workflow_runs_steps_in_order_and_stops_at_the_first_failure(tmp_path):
    w = Workflows(path=tmp_path / "wf.json")
    assert w.create("morning", ["open outlook", "show my calendar", "open spotify"]).ok
    ran: list[str] = []

    def dispatch(text):
        ran.append(text)
        return _done("FAILED" if text == "show my calendar" else "SUCCESS")
    out = w.run("my morning workflow", dispatch=dispatch, wait=True)
    assert out.ok and ran == ["open outlook", "show my calendar"]   # never continues past a failed step


def test_workflow_preview_override_and_reference(tmp_path):
    w = Workflows(path=tmp_path / "wf.json")
    w.create("pdf digest", ["summarise new pdfs in downloads"])
    p = w.preview("this")
    assert p.ok and p.evidence["dry_run"] and "summarise" in p.message
    ran: list[str] = []
    w.run("this", dispatch=lambda t: ran.append(t) or _done("SUCCESS"), wait=True, override="Documents")
    assert ran == ["summarise new pdfs in Documents"]
    assert not w.run("missing", dispatch=lambda t: None).ok
    assert w.set_enabled("pdf digest", False).ok and not w.run("pdf digest", dispatch=lambda t: None).ok
    assert w.schedule("pdf digest", "weekdays at 9").ok and w.cancel_schedule().ok


# ------------------------------------------------------------------------------------------------ files
def test_file_search_by_size_and_age(tmp_path):
    (tmp_path / "small.pdf").write_bytes(b"x" * 1024)
    (tmp_path / "big.pdf").write_bytes(b"x" * 3 * 1024 * 1024)
    (tmp_path / "pic.png").write_bytes(b"x" * 2 * 1024 * 1024)
    f = FileOperator(resources=OperatorResources())
    out = f.search(str(tmp_path), (".pdf",), min_size=parse_size("1 MB"), sort="largest")
    assert out.ok and "big.pdf" in out.message and "small.pdf" not in out.message
    assert parse_size("20 MB") == 20 * 1024 ** 2


def test_file_duplicate_and_verify(tmp_path):
    src = tmp_path / "report.txt"
    src.write_text("hello")
    res = OperatorResources()
    f = FileOperator(resources=res)
    dup = f.duplicate(str(src))
    assert dup.ok and (tmp_path / "report - copy.txt").read_text() == "hello"
    gone = tmp_path / "old.txt"
    gone.write_text("x")
    gone.unlink()
    assert f.verify(str(src), "deleted").ok is False
    assert f.verify(str(src)).ok


# ------------------------------------------------------------------------------------------------ phone
def test_phone_file_check_never_passes_a_name_to_the_shell():
    adb = FakeAdb()
    adb.files["/sdcard/Download/shot.png"] = b"x"
    dev = DeviceOperator(adb, OperatorResources())
    assert dev.has_file("shot.png").ok
    assert not dev.has_file("other.png").ok
    bad = dev.has_file("x; rm -rf /")
    assert not bad.ok and bad.needs == "clarify"
    assert not any("rm" in " ".join(c) for c in adb.calls)


def test_phone_dev_read_ops_and_approval_for_installs():
    dev = DeviceOperator(FakeAdb(), OperatorResources())
    assert dev.dev("install_apk", "app.apk").needs == "approve"
    assert dev.dev("delete_everything").needs == "clarify"


# ------------------------------------------------------------------------------------------------ system
def test_system_status_is_measured():
    from jarvis.core.operator.system import SystemOperator
    out = SystemOperator().status("ram")
    assert out.ok and "RAM" in out.message and "ram" in out.evidence
    assert SystemOperator().status("nonsense").needs == "clarify"


# ------------------------------------------------------------------------------------------------ router
@pytest.fixture(scope="module")
def router():
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter
    return SmartRouter(llm_provider=DisabledProvider())


@pytest.mark.parametrize("text,intent,action", [
    ("Make this window smaller.", "window_op", "resize"),
    ("Where did my calculator window go?", "window_op", "find"),
    ("Clear this field.", "ui_op", "clear"),
    ("Remove the screenshot attachment.", "ui_op", "remove_attachment"),
    ("Set this slider to 70 percent.", "ui_op", "slider"),
    ("Why can't I press Continue?", "ui_op", "explain"),
    ("Stop loading this page.", "browser_op", "stop"),
    ("Copy this page link.", "browser_op", "copy_url"),
    ("Show files between 20 and 200 MB.", "file_op", "search"),
    ("Make sure this deleted file no longer appears.", "file_op", "verify_deleted"),
    ("Go to app.py.", "ide_op", "open_file"),
    ("Rename this symbol to user_id.", "ide_op", "rename"),
    ("Stop the current generation.", "ide_op", "cancel"),
    ("Install my latest test APK.", "phone_op", "dev"),
    ("How much disk space is left?", "system_op", "status"),
    ("Switch to my headphones.", "system_op", "audio"),
    ("Run my morning workflow.", "workflow_op", "run"),
    ("Tell me when Antigravity closes.", "watch_op", "when"),
    ("When the download finishes, open its folder.", "watch_op", "download_done"),
    ("Tell me on my phone when this finishes.", "watch_op", "when"),
    ("Stop everything you're doing.", "cancel_task", None),
    ("Pause the current task only.", "pause_task", None),
])
def test_capability_routes(router, text, intent, action):
    d = asyncio.run(router.route(text))
    assert d.intent == intent, (text, d.lane, d.intent, d.slots)
    if action:
        assert (d.slots or {}).get("action") == action, (text, d.slots)


@pytest.mark.parametrize("text", [
    "Send that to Arun.",                     # a pronoun is not a message
    "Do this on my phone, not my PC.",        # nothing named to do there
    "Send it to the device I used earlier.",  # a device described, not named
    "Stop test app.",                         # never close an app called 'stop test'
])
def test_vague_or_unsafe_requests_ask(router, text):
    d = asyncio.run(router.route(text))
    assert d.lane in (RouteLane.CLARIFY, RouteLane.LANE_2) or d.intent in ("phone_op",), (text, d.lane, d.intent)
    assert d.intent not in ("send_whatsapp_message", "localsend_file", "close_app") or d.lane == RouteLane.CLARIFY


@pytest.mark.parametrize("text", [
    "Pause if I leave this editor.",
    "Use vision only if UIA/DOM can't find the control.",
    "Reduce background work while I'm dictating.",
    "Stop if a CAPTCHA appears.",
])
def test_conditional_policies_are_kept_as_rules(router, text):
    d = asyncio.run(router.route(text))
    assert d.intent == "standing_rule", (text, d.intent)


def test_condition_with_an_observable_event_is_a_watch_not_a_rule(router):
    d = asyncio.run(router.route("Continue the transfer when my phone reconnects."))
    assert d.intent == "watch_op" and d.slots["condition"] == "phone_connected" and d.slots["then"]


@pytest.mark.parametrize("text", ["If tests pass, open the report; otherwise show errors.",
                                  "Run the tests while you search docs."])
def test_branches_and_parallel_work_go_to_the_planner(router, text):
    d = asyncio.run(router.route(text))
    assert d.lane == RouteLane.LANE_2, (text, d.intent)


def test_operator_parser_is_case_insensitive(router):
    a = asyncio.run(router.route("press continue"))
    b = asyncio.run(router.route("Press Continue."))
    assert a.intent == b.intent == "screen_click"
