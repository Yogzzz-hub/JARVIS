"""Dimension F: Contextual pronouns, ordinals, and spatial continuity."""

import pytest
from pathlib import Path
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.models import RouteLane
from jarvis.core.context.models import ReferenceConfidence

@pytest.mark.asyncio
async def test_contextual_pronouns(router, working_memory):
    # User works with a file
    report_path = str(Path("C:/Users/ashok/Documents/report.pdf").resolve())
    working_memory.record_file(report_path)

    # User says "open it"
    dec = await router.route(CommandRequest(text="open it"))
    assert dec.intent in ("open_file", "open_app")
    if dec.intent == "open_file":
        assert dec.slots.get("path") == report_path

    # User references folder continuity
    folder_path = str(Path("C:/Users/ashok/Downloads").resolve())
    working_memory.record_folder(folder_path)
    dec_dir = await router.route(CommandRequest(text="list files in that folder"))
    assert dec_dir.intent == "list_directory"
    assert dec_dir.slots.get("path") == folder_path
