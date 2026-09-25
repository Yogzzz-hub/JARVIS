"""LEGACY_HOLDOUT: Historical 15-Query Evaluation Dataset.

QUARANTINED AS PER GENERALIZATION TORTURE TEST SPECIFICATION.
DO NOT USE AS FINAL EVIDENCE OF GENERALIZATION.
DO NOT TUNE AGAINST THIS DATASET.
"""

import pytest
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane

LEGACY_HOLDOUT_BENCHMARKS = [
    # Paraphrased system & hardware
    ("how much memory is currently available on this pc", "system_info"),
    ("what is the current time and date", "get_time"),
    ("run a complete subsystem diagnostic check", "system_diagnostics"),
    # Applications
    ("check if visual studio code is present on the computer", "check_app_installed"),
    ("where on disk can I find Google Chrome", "get_app_location"),
    ("show all programs registered in the app catalog", "list_installed_applications"),
    # Windows
    ("dismiss active window immediately", "close_window"),
    ("adjust output volume down to 15 percent", "volume_set"),
    ("take a full screen grab and store it", "take_screenshot"),
    # Files
    ("what items are saved in the documents directory", "list_directory"),
    ("tidy up downloads by sorting files into folders", "organize_downloads"),
    # Knowledge / RAG
    ("check latest rss news feeds", "rss_latest"),
    ("what are top news stories in india today", "search_news"),
    # Phone
    ("is android phone linked and reachable", "android_status"),
    ("display phone screen on my desktop", "android_open_control"),
]

# Legacy alias retained for backwards compatibility
HOLDOUT_BENCHMARKS = LEGACY_HOLDOUT_BENCHMARKS


@pytest.mark.legacy_holdout
@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_target_tool", LEGACY_HOLDOUT_BENCHMARKS)
async def test_legacy_holdout_accuracy(router, query, expected_target_tool):
    """Archived legacy holdout test. For historical reference only."""
    dec = await router.route(CommandRequest(text=query))
    assert dec.intent == expected_target_tool
    assert dec.lane in (RouteLane.LANE_0, RouteLane.LANE_1)
    assert dec.confidence >= 0.3

