"""Dimension G & H: Rapid user corrections and negative constraints."""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane

@pytest.mark.asyncio
async def test_negation_priority(router):
    # Standalone negation must strictly reject execution
    dec_neg = await router.route(CommandRequest(text="don't open spotify"))
    assert dec_neg.lane == RouteLane.REJECT
    assert "Command was negated" in dec_neg.clarification

    # Negation with positive override
    dec_override = await router.route(CommandRequest(text="don't open spotify, open chrome"))
    assert dec_override.lane == RouteLane.LANE_0
    assert dec_override.intent == "open_app"
    assert dec_override.slots.get("name") == "chrome"

    # 'open chrome instead of spotify'
    dec_instead = await router.route(CommandRequest(text="open chrome instead of spotify"))
    assert dec_instead.lane == RouteLane.LANE_0
    assert dec_instead.intent == "open_app"
    assert dec_instead.slots.get("name") == "chrome"
