"""Phase 1 (manual audit): questions about JARVIS and control of its own tasks are answered from runtime state only.

Invariants for these requests: no model call, no web search, no planner, no unrelated tool, no destructive
confirmation, no invented task state, exactly one final response.
"""
from __future__ import annotations

import asyncio

import pytest

from jarvis.core.router.introspection import classify

ORIGINAL = {
    "Tell me whether JARVIS is healthy, but don't start or restart anything.": ("system_diagnostics", {}),
    "What parts of JARVIS are unavailable right now, and which ones can still work?": ("jarvis_availability", {}),
    "Stop the current task but keep listening for my next command.": ("cancel_task", {"scope": "foreground"}),
    "Show me current CPU, memory and GPU usage without opening Task Manager.": ("resource_usage", {}),
    "Tell me what command is currently executing and how far it has actually reached.": ("task_status", {}),
    "Cancel only the background job, not the foreground task I'm waiting for.": ("cancel_task", {"scope": "background"}),
    "What failed during the previous command, and what successfully completed?": ("previous_outcome", {}),
    "Give me current JARVIS status without waking any heavy AI models.": ("system_diagnostics", {}),
}

PARAPHRASES = {
    "system_diagnostics": [
        "is jarvis healthy", "are you healthy right now", "run a self check", "jarvis, are you working properly?",
        "check your health but don't restart anything", "give me your status", "is everything ok with you",
        "how is jarvis's health", "do a self diagnosis", "jarvis status please", "are you all good", "tell me your health status",
    ],
    "jarvis_availability": [
        "which parts of jarvis are down", "what components are unavailable", "which features are working",
        "what parts of you still work", "are any of your services offline", "which modules are broken right now",
        "tell me which jarvis services are available", "what features of jarvis are disabled", "which components are degraded",
        "list the parts of jarvis that are not working", "which of your subsystems are online",
    ],
    "resource_usage": [
        "what's my cpu usage", "how much ram is being used", "show gpu usage", "how busy is the processor right now",
        "current memory usage please", "cpu and ram usage without task manager", "is the gpu busy", "how much memory is used",
        "give me live resource usage", "what's the cpu load at the moment", "how hard is my gpu working", "resource utilisation now",
    ],
    "task_status": [
        "what are you doing right now", "what task is running", "how far has the current job reached", "which step is it on",
        "what's running", "is anything still running", "what command is being executed now", "show the progress of the current task",
        "what are you working on", "is the current task still going", "what job is active", "don't stop anything, just tell me what's running",
    ],
    "stuck": [
        "is anything stuck?", "is the task stuck", "is the current job hung", "is something frozen", "is any task stuck right now",
        "the task is taking too long, is it stuck", "is my command hanging", "any job stuck?", "is the running task frozen",
        "is something not responding", "is the job stuck or still working",
    ],
    "previous_outcome": [
        "what failed in the last command", "did the previous task succeed", "what happened with the last command",
        "which steps of the previous job failed", "what went wrong with that command", "what was the result of the last task",
        "did the last request work", "what completed in the previous command", "how did the earlier task go", "what failed",
        "did my last command finish", "what was skipped in the previous task",
    ],
    "cancel_foreground": [
        "stop the current task", "cancel the task", "abort the running job", "stop the task, not jarvis",
        "cancel what you're doing", "kill the current command", "stop this task but keep listening", "cancel the current request",
        "end the running task", "halt the job", "stop the current operation", "terminate the active task",
    ],
    "cancel_background": [
        "cancel background work only", "stop the background job", "kill only background tasks", "cancel the background jobs",
        "abort background tasks but leave the current one", "stop background work, not the foreground task",
        "cancel everything in the background", "end the background job only", "stop the jobs running in the background",
        "cancel any background task", "halt the background operations",
    ],
}


@pytest.mark.parametrize("text,expected", list(ORIGINAL.items()))
def test_original_failures_route_to_runtime_state(text, expected):
    intent, slots = classify(text)
    assert intent == expected[0]
    for k, v in expected[1].items():
        assert slots[k] == v


@pytest.mark.parametrize("group,text", [(g, t) for g, ts in PARAPHRASES.items() for t in ts])
def test_paraphrases(group, text):
    hit = classify(text)
    assert hit is not None, text
    intent, slots = hit
    if group == "stuck":
        assert intent == "task_status" and slots["stuck"] is True
    elif group == "cancel_foreground":
        assert intent == "cancel_task" and slots["scope"] == "foreground" and slots["keep_listening"]
    elif group == "cancel_background":
        assert intent == "cancel_task" and slots["scope"] == "background"
    else:
        assert intent == group


@pytest.mark.parametrize("text", [
    "how do I cancel a task?", "how can I stop a background job", "what does cancelling a task do",
    "don't install anything", "don't delete anything", "stop the music", "cancel my meeting", "how are you",
    "what tasks do I have today", "show my to-do tasks", "what is my cpu", "open task manager", "stop", "is my wifi working",
])
def test_not_introspection(text):
    """Knowledge questions, negated actions and ordinary commands are not hijacked."""
    assert classify(text) is None


def test_constraints_survive():
    assert classify("Tell me whether JARVIS is healthy, but don't start or restart anything.")[1]["constraints"] == ["start", "restart"]
    assert "wake" in classify("give me jarvis status without waking any heavy AI models")[1]["constraints"]
    assert classify("don't stop anything, just tell me what's running")[1]["constraints"] == ["stop"]


# ------------------------------------------------------------------------------------------------- end to end
def _harness(tmp_path):
    from jarvis.tests.ai_harness import AIHarness
    return AIHarness(tmp_path, responder=lambda p: "LLM-WAS-CALLED")


def _running(h, text, background=False, steps=None):
    from jarvis.core.commands.contracts import CommandRequest
    from jarvis.core.metrics.clock import Clock
    from jarvis.core.tasks.manager import State
    t = h.tasks.create(CommandRequest(text=text, source="test", metadata={"background": background}), Clock())
    h.tasks.transition(t, State.UNDERSTANDING)
    h.tasks.transition(t, State.EXECUTING)
    if steps:
        t.steps_total = steps[0]
        t.steps = {f"n{i + 1}": {"label": "step", "tool": "find_file", "state": "SUCCESS", "error": None} for i in range(steps[1])}
    return t


def test_end_to_end_no_model_no_web_no_unrelated_tool(tmp_path):
    h = _harness(tmp_path)

    async def run():
        out = []
        for text in ORIGINAL:
            out.append(await h.say(text))
        return out
    results = asyncio.run(run())
    assert h.fake.chat_payloads() == [] and h.search.queries == []  # no model, no web
    tools = [r.tool_result.tool_name for r in results]
    assert tools == ["system_diagnostics", "jarvis_availability", "control", "resource_usage", "task_status", "control",
                     "previous_outcome", "system_diagnostics"]
    assert all(r.state == "SUCCESS" for r in results)  # nothing waits for a (destructive) confirmation
    assert "CPU" in results[3].message and "RAM" in results[3].message and "GB" in results[3].message
    assert results[4].message.startswith("No foreground task is currently running")
    assert "Completed all" not in " ".join(r.message for r in results)
    asyncio.run(h.close())


def test_task_status_and_scoped_cancel_use_real_tasks(tmp_path):
    h = _harness(tmp_path)
    fg = _running(h, "find my resume and send it to arun", steps=(4, 2))
    bg = _running(h, "index my documents", background=True)

    async def run():
        status = await h.say("what are you running right now and how far has it got?")
        bg_cancel = await h.say("cancel only the background job, not the foreground task")
        return status, bg_cancel
    status, bg_cancel = asyncio.run(run())
    assert "find my resume and send it to arun" in status.message and "2 of 4 steps finished" in status.message
    assert "Background job" in status.message and "index my documents" in status.message
    assert bg.cancellation.is_set() and not fg.cancellation.is_set()  # background only
    assert "index my documents" in bg_cancel.message and "keeps running" in bg_cancel.message

    bg2 = _running(h, "sync my photos", background=True)
    fg_cancel = asyncio.run(h.say("stop the current task but keep listening"))
    assert fg.cancellation.is_set() and not bg2.cancellation.is_set()  # foreground only
    assert "still listening" in fg_cancel.message
    assert h.fake.chat_payloads() == []
    asyncio.run(h.close())


def test_previous_outcome_reads_the_real_step_results(tmp_path):
    from jarvis.core.commands.contracts import CommandResult
    from jarvis.tools.base import ToolResult
    h = _harness(tmp_path)
    t = _running(h, "find the report, zip it and email it")
    t.result = CommandResult(request_id=t.request_id, state="FAILED", message="Completed 1 of 3 steps.", metrics={},
                             tool_result=ToolResult(success=False, tool_name="dag_scheduler", error="Completed 1 of 3 steps.", data={"node_results": {
                                 "n1": {"tool": "find_file", "state": "SUCCESS"},
                                 "n2": {"tool": "zip_files", "state": "FAILED", "error": "disk is full"},
                                 "n3": {"tool": "send_email", "state": "SKIPPED_DEPENDENCY_FAILED"}}}))
    r = asyncio.run(h.say("What failed during the previous command, and what successfully completed?"))
    assert "failed" in r.message and "Completed: file search" in r.message
    assert "zip files (disk is full)" in r.message and "send email (an earlier step failed)" in r.message
    assert r.message.count("The previous command") == 1  # one answer, not two
    asyncio.run(h.close())


def test_unrelated_risky_tools_are_never_proposed(tmp_path):
    h = _harness(tmp_path)
    svc = h.service
    assert svc._unanchored_risky(["install_software", "empty_recycle_bin"],
                                 "Cancel only the background job, not the foreground task I'm waiting for.") \
        == ["install_software", "empty_recycle_bin"]
    assert svc._unanchored_risky(["install_software"], "install vlc") == []
    assert svc._unanchored_risky(["empty_recycle_bin"], "empty the recycle bin") == []
    asyncio.run(h.close())


def test_one_command_one_final_response(tmp_path):
    h = _harness(tmp_path)
    finals = []
    emit = h.bus.emit

    def counting_emit(name, request_id, **data):
        if name == "response.ready":
            finals.append(request_id)
        return emit(name, request_id, **data)
    h.bus.emit = counting_emit
    r = asyncio.run(h.say("is anything stuck?"))
    task = h.tasks.get(r.request_id)
    again = h.service._finalize(task, task.state, "second answer", None, None, None, None)
    assert again is task.result and again.message == r.message  # a second finalize never emits another answer
    assert finals.count(r.request_id) == 1
    asyncio.run(h.close())


def test_graph_results_keep_their_answer():
    from types import SimpleNamespace

    from jarvis.core.commands.service import CommandService
    nr = SimpleNamespace(tool="some_status_tool", output={"summary": "Printer is online, 3 jobs queued."})
    gr = SimpleNamespace(user_message_data="Completed all 1 steps successfully.", status=SimpleNamespace(value="success"),
                         successful_nodes=["n1"], node_results={"n1": nr})
    assert CommandService._graph_message(None, gr) == "Printer is online, 3 jobs queued."
