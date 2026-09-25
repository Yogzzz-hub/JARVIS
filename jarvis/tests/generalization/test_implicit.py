"""Dimension C: Implicit and indirect intent."""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane

@pytest.mark.asyncio
async def test_implicit_volume_and_desktop(router):
    # Volume control through indirect phrasing
    dec = await router.route(CommandRequest(text="turn the volume down to 20"))
    assert dec.intent == "volume_set"
    assert dec.slots.get("percent") == 20

    # Screenshot via indirect phrasing
    dec_snap = await router.route(CommandRequest(text="capture my monitor right now"))
    assert dec_snap.intent == "take_screenshot"

    # Status check via indirect phrasing
    dec_stat = await router.route(CommandRequest(text="check if my phone is connected"))
    assert dec_stat.intent == "android_status"
