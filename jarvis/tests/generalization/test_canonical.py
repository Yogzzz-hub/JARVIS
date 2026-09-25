"""Dimension A: Canonical baseline commands."""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane

@pytest.mark.asyncio
@pytest.mark.parametrize("command,expected_tool,expected_lane", [
    ("time", "get_time", RouteLane.LANE_0),
    ("open notepad", "open_app", RouteLane.LANE_0),
    ("open chrome", "open_app", RouteLane.LANE_0),
    ("volume 50", "volume_set", RouteLane.LANE_0),
    ("take screenshot", "take_screenshot", RouteLane.LANE_0),
    ("show desktop", "show_desktop", RouteLane.LANE_0),
    ("minimize window", "minimize_window", RouteLane.LANE_0),
    ("maximize window", "maximize_window", RouteLane.LANE_0),
    ("close window", "close_window", RouteLane.LANE_0),
    ("diagnostics", "system_diagnostics", RouteLane.LANE_0),
])
async def test_canonical_commands(router, command, expected_tool, expected_lane):
    dec = await router.route(CommandRequest(text=command))
    assert dec.lane == expected_lane
    assert dec.intent == expected_tool
    assert dec.confidence >= 0.95
