"""Dimension I & J: Ambiguous requests and out-of-scope unknowns."""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane

@pytest.mark.asyncio
async def test_ambiguity_clarification(router):
    # Inherently ambiguous app name
    dec_ambig = await router.route(CommandRequest(text="open studio"))
    assert dec_ambig.lane == RouteLane.CLARIFY
    assert "Which" in dec_ambig.clarification and ("mean" in dec_ambig.clarification)

    # Missing required parameter on capability
    dec_check = await router.route(CommandRequest(text="is installed on this machine"))
    assert dec_check.lane == RouteLane.CLARIFY

@pytest.mark.asyncio
async def test_unknown_out_of_scope(router):
    # Out of scope domain request
    dec_unk = await router.route(CommandRequest(text="bake me a pizza for dinner"))
    assert dec_unk.lane == RouteLane.CLARIFY
    assert dec_unk.confidence < 0.5
