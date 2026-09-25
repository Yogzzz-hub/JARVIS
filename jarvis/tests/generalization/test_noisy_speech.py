"""Dimension D: Noisy ASR and spelling variants."""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane

@pytest.mark.asyncio
@pytest.mark.parametrize("noisy_text,expected_tool", [
    ("ope notpad", "open_app"),
    ("opn chrome", "open_app"),
    ("valume 40", "volume_set"),
    ("vol 70", "volume_set"),
    ("take screenshit", "take_screenshot"),
])
async def test_noisy_speech_tolerance(router, noisy_text, expected_tool):
    dec = await router.route(CommandRequest(text=noisy_text))
    assert dec.intent == expected_tool
