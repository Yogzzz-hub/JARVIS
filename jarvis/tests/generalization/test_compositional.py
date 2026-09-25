"""Dimension E: Multi-clause compositional commands."""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane, ComplexityLevel

@pytest.mark.asyncio
async def test_compositional_compound_routing(router):
    # Compound multi-step commands must be flagged for Lane 2 / Complex DAG
    dec = await router.route(CommandRequest(text="open Chrome and search for lo-fi music on YouTube"))
    assert dec.lane in (RouteLane.LANE_2, RouteLane.LANE_0)
    assert dec.complexity in (ComplexityLevel.COMPOUND, ComplexityLevel.COMPLEX)

    dec2 = await router.route(CommandRequest(text="take a screenshot and open downloads"))
    assert dec2.complexity in (ComplexityLevel.COMPOUND, ComplexityLevel.COMPLEX)
