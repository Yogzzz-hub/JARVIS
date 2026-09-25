"""Dimension B: Unseen natural language paraphrases."""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane

@pytest.mark.asyncio
@pytest.mark.parametrize("phrase,expected_tool", [
    ("could you please see what files are in downloads", "list_directory"),
    ("turn down the sound to 30 percent please", "volume_set"),
    ("take a snapshot of the primary screen", "take_screenshot"),
    ("is vlc installed on this machine", "check_app_installed"),
    ("where is vlc located on disk", "get_app_location"),
    ("clean up my downloads folder by sorting files", "organize_downloads"),
    ("show me my phone battery level", "android_status"),
    ("what are the latest news headlines in india", "search_news"),
    ("give me my morning briefing", "morning_briefing"),
])
async def test_paraphrase_generalization(router, phrase, expected_tool):
    dec = await router.route(CommandRequest(text=phrase))
    assert dec.intent == expected_tool
    assert dec.lane in (RouteLane.LANE_0, RouteLane.LANE_1)
    assert dec.confidence >= 0.3
