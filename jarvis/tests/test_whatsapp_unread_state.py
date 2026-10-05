"""'Summarize my WhatsApp' reports what WhatsApp itself shows as unread: every person with unread messages and what
they said - not only messages that look like questions - using the bridge's unread badges when it reports them.
Messages missed while JARVIS was offline are stored for questions but never answered, announced or run."""
from __future__ import annotations

import asyncio
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from jarvis.integrations.whatsapp.inbox import UrgencyClassifier, WhatsAppInbox
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.tools.system import whatsapp_tools as wt

ASHOK = "919000000001@s.whatsapp.net"
SANJANA = "919000000002@s.whatsapp.net"
YOGA = "919000000003@s.whatsapp.net"
SIH = "120363000000000001@g.us"
LOTT = "120363000000000002@g.us"


def _msg(mid, chat, name, text, ts, *, sender=None, chat_name="", me=False, history=False):
    return NormalizedWhatsAppMessage(message_id=mid, chat_id=chat, sender_id=sender or chat, sender_display_name=name,
                                     timestamp=str(ts), text=text, is_group=chat.endswith("@g.us"), chat_name=chat_name,
                                     is_from_me=me, history=history)


def _screenshot_inbox(tmp_path) -> WhatsAppInbox:
    """The chats from the report: nothing in them is phrased like an English question."""
    now = time.time()
    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    inbox.add_message(_msg("a1", ASHOK, "Ashok", "OK, I will check", now - 600))
    inbox.add_message(_msg("s1", SANJANA, "Sanjana", "Hi", now - 1400))
    inbox.add_message(_msg("s2", SANJANA, "Sanjana", "Ena man panra", now - 1300))
    inbox.add_message(_msg("g1", SIH, "Devi", "Meeting at 5", now - 100, sender="919000000009@s.whatsapp.net",
                           chat_name="RIT SIH & Techgium 2026"))
    return inbox


def _badges(now=None):
    now = now or time.time()
    return [
        {"chat_id": ASHOK, "name": "Ashok Kumar", "unread": 1, "last_ts": now - 600, "last_text": "OK, I will check"},
        {"chat_id": SANJANA, "name": "Sanjana Ssk", "unread": 2, "last_ts": now - 1300, "last_text": "Ena man panra"},
        {"chat_id": YOGA, "name": "Yoga CEO", "unread": 1, "last_ts": now - 2000, "last_text": ""},
        {"chat_id": SIH, "name": "RIT SIH & Techgium 2026", "unread": 2, "is_group": True, "last_ts": now - 100,
         "last_text": "Meeting at 5", "last_sender": "Devi"},
        {"chat_id": LOTT, "name": "Lottangais", "unread": 1, "is_group": True, "last_ts": now - 50, "last_text": "lol",
         "last_sender": "Karthik"},
    ]


def test_the_reported_case_lists_everyone_with_unread_messages(tmp_path):
    spoken = wt.SummarizeWhatsAppMessagesTool(inbox=_screenshot_inbox(tmp_path)).run({})["spoken_summary"]
    assert "No one is waiting" not in spoken
    assert spoken.startswith("You have 3 unread messages from 2 people.")
    assert 'Sanjana sent 2 messages; the latest asks "Ena man panra"' in spoken  # Tanglish question, first
    assert 'Ashok says "OK, I will check"' in spoken
    assert "Meeting at 5" not in spoken and "1 group chat also has 1 unread message" in spoken


def test_whatsapp_badges_give_the_exact_counts_and_names_the_phone_shows(tmp_path):
    inbox = _screenshot_inbox(tmp_path)
    inbox.update_chats(_badges(), full=True, synced=True)
    out = wt.SummarizeWhatsAppMessagesTool(inbox=inbox).run({})
    spoken = out["spoken_summary"]
    assert out["unread_count"] == 4
    assert spoken.startswith("You have 4 unread messages from 3 people.")
    assert "Sanjana Ssk sent 2 messages" in spoken and 'Ashok Kumar says "OK, I will check"' in spoken
    assert "Yoga CEO: 1 unread message" in spoken  # unread on the phone though JARVIS never received it
    assert ("2 group chats also have 3 unread messages (Lottangais: 1, RIT SIH & Techgium 2026: 2)"
            " - ask if you want them.") in spoken
    both = wt.SummarizeWhatsAppMessagesTool(inbox=inbox).run({"include_groups": True})["spoken_summary"]
    assert both.startswith("You have 7 unread WhatsApp messages in 5 chats.") and 'Karthik in Lottangais says "lol"' in both


def test_reading_on_the_phone_clears_it_and_unanswered_questions_are_still_mentioned(tmp_path):
    inbox = _screenshot_inbox(tmp_path)
    inbox.update_chats(_badges(), full=True, synced=True)
    inbox.update_chats([{"chat_id": SANJANA, "name": "Sanjana Ssk", "unread": 0, "last_ts": time.time()}])
    spoken = inbox.summarize_inbox()["spoken_summary"]
    assert spoken.startswith("You have 2 unread messages from 2 people.") and "Ena man panra" not in spoken
    assert "Still waiting for your reply: Sanjana Ssk." in spoken
    # a full list from WhatsApp: any chat missing from it is read
    inbox.update_chats([c for c in _badges() if c["chat_id"] == ASHOK], full=True, synced=True)
    spoken = inbox.summarize_inbox()["spoken_summary"]
    assert spoken.startswith("You have 1 unread message.") and "Yoga" not in spoken and "group" not in spoken


def test_badge_keeps_only_the_newest_messages_unread(tmp_path):
    inbox = _screenshot_inbox(tmp_path)
    inbox.update_chats([{"chat_id": SANJANA, "name": "Sanjana Ssk", "unread": 1, "last_ts": time.time()}], synced=True)
    assert [m.text for m in inbox.get_unread(limit=10) if m.chat_id == SANJANA] == ["Ena man panra"]


def test_without_a_full_chat_list_other_chats_use_the_inbox(tmp_path):
    inbox = _screenshot_inbox(tmp_path)
    inbox.update_chats([{"chat_id": YOGA, "name": "Yoga CEO", "unread": 1, "last_ts": time.time()}])  # not synced
    spoken = inbox.summarize_inbox()["spoken_summary"]
    assert "Yoga CEO" in spoken and "Sanjana" in spoken and "Ashok" in spoken


def test_incomplete_sync_never_claims_zero_unread(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "partial.db")
    out = wt.SummarizeWhatsAppMessagesTool(inbox=inbox).run({})
    assert out["status"] == "PARTIAL_SYNC"
    assert out["unread_count"] == 0
    assert "can't verify" in out["spoken_summary"]
    count = wt.ReadWhatsAppMessagesTool(inbox=inbox).run({"filter": "unread", "count_only": True})
    assert count["status"] == "PARTIAL_SYNC"
    assert "can't verify" in count["spoken_summary"]


def test_stale_zero_badge_does_not_hide_newer_stored_message_during_partial_sync(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "partial.db")
    inbox.update_chats([{"chat_id": ASHOK, "name": "Ashok", "unread": 0}], synced=False)
    inbox.add_message(_msg("new", ASHOK, "Ashok", "Please send the file", time.time()))
    out = wt.SummarizeWhatsAppMessagesTool(inbox=inbox).run({})
    assert out["status"] == "PARTIAL_SYNC"
    assert out["unread_count"] == 1
    assert "Ashok" in out["spoken_summary"]
    # A cached full snapshot can also arrive *after* the new message.
    inbox.update_chats([{"chat_id": ASHOK, "name": "Ashok", "unread": 0}], full=True, synced=False)
    assert inbox.summarize_inbox()["unread_count"] == 1


def test_disconnect_invalidates_cached_complete_sync(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "state.db")
    inbox.update_chats([], full=True, synced=True)
    assert inbox.sync_state() == "READY"
    inbox.set_connector_state("DISCONNECTED")
    assert inbox.sync_state() == "NOT_CONNECTED"
    inbox.set_connector_state("CONNECTED")
    assert inbox.sync_state() == "PARTIAL_SYNC"


def test_ready_requires_snapshot_from_current_generation(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "generation.db")
    inbox.set_connector_state("CONNECTED")
    inbox.update_chats([], full=True, synced=True, generation="new", synced_generation="old")
    assert inbox.sync_state() == "PARTIAL_SYNC"
    inbox.update_chats([], full=True, synced=True, generation="new", synced_generation="new",
                       event_meta={"last_history_event": "2026-10-01T00:00:00Z"})
    assert inbox.sync_state() == "READY"
    diag = inbox.diagnostics()
    assert diag["sync_generation"] == "new"
    assert diag["last_history_event"] == "2026-10-01T00:00:00Z"


def test_legacy_bridge_snapshot_cannot_claim_ready_after_connection(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "legacy.db")
    inbox.set_connector_state("CONNECTED")
    inbox.update_chats([{"chat_id": ASHOK, "unread": 0}], full=True, synced=True)
    assert inbox.sync_state() == "PARTIAL_SYNC"


def test_wait_for_sync_wakes_on_current_snapshot(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "wait.db")
    inbox.set_connector_state("CONNECTED")
    timer = threading.Timer(0.02, lambda: inbox.update_chats([], full=True, synced=True,
                                                             generation="g1", synced_generation="g1"))
    timer.start()
    try:
        assert inbox.wait_for_ready(0.5)
    finally:
        timer.join()


def test_writing_in_a_chat_reads_it(tmp_path):
    inbox = _screenshot_inbox(tmp_path)
    inbox.add_message(_msg("o1", SANJANA, "me", "just chilling", time.time(), me=True))
    spoken = inbox.summarize_inbox()["spoken_summary"]
    assert "Sanjana" not in spoken and spoken.startswith("You have 1 unread message.")


def test_count_uses_whatsapp_badges(tmp_path):
    inbox = _screenshot_inbox(tmp_path)
    inbox.update_chats(_badges(), full=True, synced=True)
    out = wt.ReadWhatsAppMessagesTool(inbox=inbox).run({"filter": "unread", "count_only": True})
    assert out["count"] == 4
    assert out["spoken_summary"] == ("You have 4 unread WhatsApp messages in your personal chats from 3 people: "
                                     "Ashok Kumar 1, Sanjana Ssk 2, Yoga CEO 1. Group chats have 3 more in 2 groups.")
    read = wt.ReadWhatsAppMessagesTool(inbox=inbox).run({})  # "read my messages": the unread ones
    assert read["filter"] == "unread" and {m["sender"] for m in read["messages"]} == {"Ashok Kumar", "Sanjana Ssk"}


def test_tanglish_questions_and_requests_need_a_reply():
    assert UrgencyClassifier.analyze("Ena man panra")[1] is True
    assert UrgencyClassifier.analyze("eppo varuva")[1] is True
    assert UrgencyClassifier.analyze("notes anuppu da")[1] is True
    assert UrgencyClassifier.analyze("OK, I will check")[1] is False
    assert UrgencyClassifier.analyze("reached home")[1] is False


def test_bridge_times_are_real_times(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "t.db")
    item = inbox.add_message(_msg("t1", ASHOK, "Ashok", "hi", "2026-09-29T16:27:00.000Z"))
    assert item.timestamp == datetime(2026, 9, 29, 16, 27, tzinfo=timezone.utc).timestamp()


def test_seen_again_keeps_read_and_replied_state(tmp_path):
    inbox = _screenshot_inbox(tmp_path)
    inbox.mark_chat_read(ASHOK)
    inbox.add_message(_msg("a1", ASHOK, "Ashok", "OK, I will check", time.time() - 600, history=True))
    assert all(m.chat_id != ASHOK for m in inbox.get_unread(limit=10))


def test_old_databases_do_not_report_months_of_unread(tmp_path):
    db = tmp_path / "old.db"
    WhatsAppInbox(db)
    with sqlite3.connect(db) as conn:  # an inbox from before unread tracking
        conn.execute("PRAGMA user_version = 0")
        conn.execute("INSERT INTO whatsapp_messages (message_id, chat_id, sender_id, sender_display_name, timestamp, type, "
                     "text, summary) VALUES ('old', ?, ?, 'Old', ?, 'text', 'from last month', '')",
                     (ASHOK, ASHOK, time.time() - 30 * 24 * 3600))
        conn.execute("INSERT INTO whatsapp_messages (message_id, chat_id, sender_id, sender_display_name, timestamp, type, "
                     "text, summary) VALUES ('new', ?, ?, 'Sanjana', ?, 'text', 'from this morning', '')",
                     (SANJANA, SANJANA, time.time() - 3600))
    inbox = WhatsAppInbox(db)
    assert [m.text for m in inbox.get_unread(limit=10)] == ["from this morning"]


def test_missed_messages_are_stored_but_never_acted_on(tmp_path):
    from jarvis.integrations.whatsapp.fake_transport import FakeWhatsAppTransport
    from jarvis.integrations.whatsapp.gateway import WhatsAppChannelGateway

    class Commands:
        calls = []

        async def handle(self, *a, **k):
            Commands.calls.append(a)

    class AI:
        calls = 0

        async def auto_reply(self, *a, **k):
            AI.calls += 1
            return "draft"

    announced = []
    transport = FakeWhatsAppTransport()
    gw = WhatsAppChannelGateway(transport=transport, command_service=Commands(), owner_identities={"916381456199"},
                                inbox=WhatsAppInbox(tmp_path / "gw.db"), whatsapp_ai=AI(), announcer=announced.append)
    now = time.time()
    out = asyncio.run(gw.handle_incoming(_msg("h1", ASHOK, "Ashok", "urgent: can you call me?", now - 3600, history=True)))
    assert out["status"] == "HISTORY_STORED"
    # the owner's own message from while JARVIS was off: stored, never a command
    own = _msg("h2", "916381456199@s.whatsapp.net", "me", "shutdown my pc", now - 3500,
               sender="916381456199@s.whatsapp.net", me=True, history=True)
    assert asyncio.run(gw.handle_incoming(own))["status"] == "HISTORY_STORED"
    assert Commands.calls == [] and AI.calls == 0 and announced == []
    assert not getattr(transport, "sent_messages", [])
    assert [m.text for m in gw.inbox.get_unread(limit=5)] == ["urgent: can you call me?"]
    assert asyncio.run(gw.handle_incoming(_msg("h1", ASHOK, "Ashok", "urgent: can you call me?", now - 3600)))["status"] \
        == "DUPLICATE_IGNORED"


def test_chat_state_from_the_bridge_reaches_the_inbox(tmp_path):
    from jarvis.integrations.whatsapp.service import BaileysWebSocketTransport, WhatsAppIntegrationService

    inbox = _screenshot_inbox(tmp_path)

    class Service:
        gateway = type("G", (), {"inbox": inbox})()

    async def run():
        transport = BaileysWebSocketTransport(on_chat_state=lambda p: WhatsAppIntegrationService._on_chat_state(Service(), p))
        await transport._handle_event({"type": "chat_state", "payload": {"synced": True, "full": True, "chats": _badges()}})
        await asyncio.sleep(0.2)

    asyncio.run(run())
    assert inbox.chats_synced() and inbox.summarize_inbox()["unread_count"] == 4


@pytest.mark.parametrize("text,intent,slots", [
    ("summarize my whatsapp", "summarize_whatsapp_messages", {}),
    ("what's new on whatsapp", "summarize_whatsapp_messages", {}),
    ("what did i miss on whatsapp", "summarize_whatsapp_messages", {}),
    ("whatsapp la enna puthusa", "summarize_whatsapp_messages", {}),
    ("read my unread messages", "read_whatsapp_messages", {"filter": "unread"}),
    ("how many unread messages do i have", "read_whatsapp_messages", {"filter": "unread", "count_only": True}),
    ("how many unread personal messages can you currently see", "read_whatsapp_messages", {"filter": "unread", "count_only": True}),
    ("whatsapp la evlo message vandhirukku", "read_whatsapp_messages", {"filter": "unread", "count_only": True}),
    ("who is waiting for my reply", "read_whatsapp_messages", {"filter": "needs_reply"}),
    ("catch me up on WhatsApp", "summarize_whatsapp_messages", {}),
    ("anything new in my personal chats", "summarize_whatsapp_messages", {}),
    ("who has messaged me", "summarize_whatsapp_messages", {}),
    ("give me the WhatsApp rundown", "summarize_whatsapp_messages", {}),
    ("what's waiting for me on WhatsApp", "summarize_whatsapp_messages", {}),
])
def test_unread_questions_route(text, intent, slots):
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.core.router.router import SmartRouter

    d = asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route(text))
    assert d.intent == intent and d.slots == slots


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_bridge_tracks_whatsapp_unread_badges():
    bridge = Path(__file__).resolve().parents[2] / "integrations/whatsapp/bridge"
    tests = sorted(str(p.relative_to(bridge)) for p in (bridge / "test").glob("*.test.js"))
    run = subprocess.run(["node", "--test", *tests], cwd=bridge, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
