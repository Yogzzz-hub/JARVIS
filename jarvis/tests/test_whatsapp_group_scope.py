"""Group chats are only read, summarised or written to when the owner names them; summaries are per person."""
from __future__ import annotations

import asyncio

from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage
from jarvis.tools.system import whatsapp_tools as wt

GROUP = "120363000000000777@g.us"


def _msg(mid, chat, sender, name, text, ts, chat_name=""):
    return NormalizedWhatsAppMessage(message_id=mid, chat_id=chat, sender_id=sender, sender_display_name=name,
                                     timestamp=str(ts), text=text, is_group=chat.endswith("@g.us"), chat_name=chat_name)


def _inbox(tmp_path):
    inbox = WhatsAppInbox(tmp_path / "inbox.db")
    inbox.add_message(_msg("g1", GROUP, "devi@s.whatsapp.net", "Devi",
                           "Urgent: Dr. Nisha wants Team 62 to contact her immediately", 1000, "CSE A"))
    inbox.add_message(_msg("g2", GROUP, "devi@s.whatsapp.net", "Devi",
                           "Students registered for the National Innovation Challenge, give your names to the class rep?", 1001, "CSE A"))
    inbox.add_message(_msg("d1", "arun@s.whatsapp.net", "arun@s.whatsapp.net", "Arun", "Are you coming to the lab today?", 1002))
    inbox.add_message(_msg("d2", "mom@s.whatsapp.net", "mom@s.whatsapp.net", "Mom", "Call me urgent", 1003))
    return inbox


def test_group_scope_is_only_what_the_owner_named():
    assert wt.group_scope_from_text("Summarize my WhatsApp.") == {}
    assert wt.group_scope_from_text("summarize my group messages") == {"include_groups": True}
    assert wt.group_scope_from_text("read messages in the CSE group") == {"group": "cse"}
    assert wt.group_scope_from_text("what did they say in NIC 2026 group") == {"group": "nic 2026"}
    assert wt.group_scope_from_text("reply in that group saying ok") == {"group": "that"}


def test_summary_is_personal_chats_only_and_attributed_per_person(tmp_path):
    inbox = _inbox(tmp_path)
    out = wt.SummarizeWhatsAppMessagesTool(inbox=inbox).run({})
    spoken = out["spoken_summary"]
    assert "2 people are waiting" in spoken and "Mom" in spoken and "Arun" in spoken
    assert spoken.index("Mom") < spoken.index("Arun")  # urgent first
    assert "Nisha" not in spoken and "Team 62" not in spoken  # group content is not read out
    assert "1 group chat has new messages" in spoken


def test_named_group_summary_and_unknown_group(tmp_path):
    inbox = _inbox(tmp_path)
    tool = wt.SummarizeWhatsAppMessagesTool(inbox=inbox)
    spoken = tool.run({"group": "cse a"})["spoken_summary"]
    assert "Devi in CSE A (2 messages)" in spoken and "Arun" not in spoken
    assert "couldn't find" in tool.run({"group": "football"})["spoken_summary"]


def test_read_tool_skips_groups_unless_asked(tmp_path):
    inbox = _inbox(tmp_path)
    tool = wt.ReadWhatsAppMessagesTool(inbox=inbox)
    assert {m["sender"] for m in tool.run({"filter": "needs_reply", "limit": 10})["messages"]} == {"Mom", "Arun"}
    both = tool.run({"filter": "needs_reply", "limit": 10, "include_groups": True})["messages"]
    assert {m["sender"] for m in both} == {"Mom", "Arun", "Devi"}


def test_send_to_a_group_needs_the_owner_to_name_it(tmp_path, monkeypatch):
    inbox = _inbox(tmp_path)
    monkeypatch.setattr(WhatsAppInbox, "get_default", classmethod(lambda cls: inbox))

    class Transport:
        sent = []

        async def send_text(self, to, text):
            self.sent.append(to)
            return {"status": "SENT", "message_id": "x"}
    tr = Transport()
    tool = wt.SendWhatsAppMessageTool(transport=tr)
    blocked = tool.run({"recipient": GROUP, "message": "hi"})
    assert blocked["status"] == "FAILED" and blocked["evidence"]["group_blocked"] and tr.sent == []
    named = tool.run({"recipient": "the CSE A group", "message": "hi"})
    assert named["status"] == "SENT" and tr.sent == [GROUP]


def test_personal_reply_never_lands_in_a_group(tmp_path):
    inbox = _inbox(tmp_path)
    assert inbox.find_latest_incoming("devi", direct_only=True) is None


def test_gateway_stores_group_messages_silently(tmp_path):
    from jarvis.integrations.whatsapp.fake_transport import FakeWhatsAppTransport
    from jarvis.integrations.whatsapp.gateway import WhatsAppChannelGateway

    announced = []

    class AI:
        calls = 0

        async def auto_reply(self, *a, **k):
            AI.calls += 1
            return "draft"

    gw = WhatsAppChannelGateway(transport=FakeWhatsAppTransport(), command_service=None, owner_identities={"919999999999"},
                                inbox=WhatsAppInbox(tmp_path / "gw.db"))
    gw.announcer = announced.append
    gw.whatsapp_ai = AI()
    out = asyncio.run(gw.handle_incoming(_msg("g9", GROUP, "devi@s.whatsapp.net", "Devi", "urgent please reply", 1000, "CSE A")))
    assert out["status"] == "GROUP_STORED" and announced == [] and AI.calls == 0
    assert gw.inbox.get_recent(limit=5, group=GROUP)[0].chat_name == "CSE A"


def test_router_only_targets_a_group_when_it_is_named():
    from jarvis.core.router.extended import match_bulk_reply
    d = match_bulk_reply("reply in the CSE group saying I'll be there", "r")
    assert d.intent == "reply_whatsapp_message" and d.slots == {"recipient": "the CSE group", "instruction": "I'll be there"}
    d = match_bulk_reply("send a message to the family group saying happy diwali", "r")
    assert d.intent == "send_whatsapp_message" and d.slots == {"recipient": "the family group", "message": "happy diwali"}
    d = match_bulk_reply("summarize the CSE group", "r")
    assert d.intent == "summarize_whatsapp_messages" and d.slots == {"group": "cse"}
    assert match_bulk_reply("summarize my whatsapp", "r") is None
    assert match_bulk_reply("reply to devi saying ok", "r") is None
