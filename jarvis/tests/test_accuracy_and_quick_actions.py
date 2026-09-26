"""Router generalisation (typos, negation, corrections, paraphrases), RAG precision/abstention, grounded chat that
does not invent personal facts, and the fast browser / Windows / phone quick actions."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.core.router.normalize import correct_command_typos, normalize_text
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter


@pytest.fixture(scope="module")
def router():
    return SmartRouter(llm_provider=DisabledProvider())


def route(router, text):
    return asyncio.run(router.route(text))


# ------------------------------------------------------------------ generalisation
@pytest.mark.parametrize("text,intent", [
    ("launsh chrom", "open_app"), ("strt spotfy", "open_app"), ("mut volum", "volume_mute"), ("unmut valume", "volume_unmute"),
    ("shwo desktp", "show_desktop"), ("wher is chrom installed", "get_app_location"), ("chekc if vlc installed", "check_app_installed"),
    ("andrpid phon status", "android_status"), ("Open Calculator but not Notepad.", "open_app"),
    ("Please run Chrome but definitely not Firefox.", "open_app"), ("Don't mute the sound, just turn it down to 20.", "volume_set"),
    ("Check whether Firefox is on this computer", "check_app_installed"), ("Find the location of Chrome on disk", "get_app_location"),
    ("List every program installed on PC", "list_installed_applications"), ("Back to desktop.", "show_desktop"),
    ("Kill current active window", "close_window"), ("Check processor specifications", "system_info"),
    ("Rebuild application index cache", "refresh_applications"), ("Need to do some math calculations.", "open_app"),
    ("Get VLC media player rolling.", "open_app"), ("Send active app to taskbar", "minimize_window"),
])
def test_generalisation(router, text, intent):
    assert route(router, text).intent == intent


def test_typo_repair_never_touches_message_content_or_real_words():
    assert correct_command_typos("tell karthik saying lunch at 2") == "tell karthik saying lunch at 2"
    assert correct_command_typos("open youtube") == "open youtube"
    assert normalize_text("send a message to yoga saying varuviya")[1] == "send a message to yoga saying varuviya"


def test_ordinal_without_a_list_asks_instead_of_opening_an_app(router):
    d = route(router, "open the second one")
    assert d.intent == "open_file" and d.lane.value == "CLARIFY" and d.slots == {"ordinal": 2}
    assert route(router, "Open the second file—sorry, the third.").slots == {"ordinal": 3}
    assert route(router, "Pick the first result, wait, take the last one.").slots == {"ordinal": -1}


# ------------------------------------------------------------------ RAG
def test_rag_benchmark_precision_recall_and_abstention():
    from tests.rag.benchmark import run
    base, new = run(baseline=True), run()
    assert new["recall"] >= 0.95 and new["precision"] >= 0.95
    assert new["precision"] > base["precision"] and new["abstention"] >= base["abstention"]


def test_rerank_drops_unrelated_chunks():
    from jarvis.core.knowledge.models import KnowledgeItem
    from jarvis.core.knowledge.rerank import rerank
    items = [KnowledgeItem(source_type="RAG_CHUNK", resource_id=str(i), title=t, snippet=s, relevance=0.5)
             for i, (t, s) in enumerate([("refund_policy.md (Refund policy)", "Refunds within 30 days of purchase."),
                                         ("gym_plan.txt", "Monday chest and triceps."),
                                         ("refund_policy.md (Refund policy)", "Refunds within 30 days of purchase!")])]
    out = rerank("what is the refund window", items)
    assert [i.resource_id for i in out] == ["0"]  # unrelated and near-duplicate chunks removed


def test_personal_question_without_evidence_is_not_answered_by_the_model():
    from jarvis.core.llm.assistant import Assistant, is_personal_question

    class Boom:
        async def chat(self, *a, **k):
            raise AssertionError("the model must not be asked to invent a personal fact")

    assert is_personal_question("what is my blood group") and not is_personal_question("explain recursion")
    reply = asyncio.run(Assistant(client=Boom()).respond("what is my blood group", use_web=False))
    assert "couldn't find" in reply.text


# ------------------------------------------------------------------ quick actions
@pytest.mark.parametrize("text,tool,slots", [
    ("open a new tab", "browser_quick_action", {"action": "new_tab"}),
    ("close this tab", "browser_quick_action", {"action": "close_tab"}),
    ("reopen the closed tab", "browser_quick_action", {"action": "reopen_tab"}),
    ("go to tab 3", "browser_quick_action", {"action": "go_to_tab", "tab": 3}),
    ("refresh the page", "browser_quick_action", {"action": "reload"}),
    ("bookmark this page", "browser_quick_action", {"action": "bookmark"}),
    ("open incognito window", "browser_quick_action", {"action": "incognito"}),
    ("scroll down", "browser_quick_action", {"action": "scroll_down"}),
    ("open task manager", "pc_quick_action", {"action": "task_manager"}),
    ("Show clipboard saved items", "pc_quick_action", {"action": "clipboard_history"}),
    ("take a snip", "pc_quick_action", {"action": "snip"}),
    ("new virtual desktop", "pc_quick_action", {"action": "new_desktop"}),
    ("switch to the next desktop", "pc_quick_action", {"action": "next_desktop"}),
    ("set my phone brightness to 40", "android_quick_action", {"action": "brightness", "value": "40"}),
    ("set phone volume to 8", "android_quick_action", {"action": "media_volume", "value": "8"}),
    ("open wifi settings on my phone", "android_quick_action", {"action": "settings", "value": "wifi"}),
    ("what app is open on my phone", "android_quick_action", {"action": "current_app"}),
    ("send sms to 9876543210 saying I'm running late",
     "android_quick_action", {"action": "sms_draft", "number": "9876543210", "text": "I'm running late"}),
])
def test_quick_action_routing(router, text, tool, slots):
    d = route(router, text)
    assert d.intent == tool and d.slots == slots


def test_existing_commands_are_unchanged(router):
    assert route(router, "open downloads").intent == "open_known_folder"
    assert route(router, "close window").intent == "close_window"
    assert route(router, "turn off wifi on my phone").intent == "android_toggle"
    assert route(router, "tell mom I'll be late").intent == "send_whatsapp_message"


def test_quick_action_tools_are_registered_and_safe_off_windows():
    from jarvis.tools.system.quick_actions import BrowserQuickActionTool, PCQuickActionTool, create_quick_action_tools
    assert {t.definition.name for t in create_quick_action_tools()} == {"browser_quick_action", "pc_quick_action", "android_quick_action"}
    import os
    if os.name != "nt":
        assert BrowserQuickActionTool().run({"action": "new_tab"})["status"] == "FAILED"
        assert PCQuickActionTool().run({"action": "task_manager"})["status"] == "FAILED"


def test_phone_quick_actions_use_fixed_validated_adb_templates():
    from jarvis.connectors.android.scrcpy import AndroidScrcpyConnector
    conn = AndroidScrcpyConnector.__new__(AndroidScrcpyConnector)
    calls = []
    conn._run_adb = lambda args, timeout=5.0: (calls.append(args) or (0, "", ""))
    assert conn._quick_action({"what": "brightness", "value": 40})["success"]
    assert calls[-1] == ["shell", "settings", "put", "system", "screen_brightness", "102"]
    conn._quick_action({"what": "settings", "value": "wifi"})
    assert calls[-1] == ["shell", "am", "start", "-a", "android.settings.WIFI_SETTINGS"]
    conn._quick_action({"what": "sms_draft", "number": "+91 98765 43210", "text": "I'm late"})
    assert calls[-1][-1] == "'I'\\''m late'" and calls[-1][6] == "sms:+919876543210"
    with pytest.raises(ValueError):
        conn._quick_action({"what": "sms_draft", "number": "9876543210", "text": "hi $(reboot)"})
    with pytest.raises(ValueError):
        conn._quick_action({"what": "sms_draft", "number": "9876543210", "text": "hi `reboot`"})
    with pytest.raises(ValueError):
        conn._quick_action({"what": "settings", "value": "rm -rf"})
