"""Playwright File Uploads with Phase-5 Policy Guard."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from playwright.async_api import FileChooser, Page
from jarvis.core.computer.models import BrowserFailureReason, InteractionOutcome

logger = logging.getLogger("jarvis.computer.browser.uploads")


class BrowserUploadHandler:
    """Safely handles web file uploads with policy validation and file chooser binding."""

    @classmethod
    async def upload_file(
        cls,
        page: Page,
        trigger_action: Any,
        source_file: Path,
        confirmed: bool = False,
    ) -> InteractionOutcome:
        """Upload a local file using Playwright's FileChooser with confirmation guard."""
        if not source_file.exists() or not source_file.is_file():
            return InteractionOutcome(
                success=False,
                action="browser_upload",
                verification_status="FAILED",
                message=f"Source upload file '{source_file}' does not exist.",
            )

        if not confirmed:
            return InteractionOutcome(
                success=False,
                action="browser_upload",
                verification_status="CONFIRMATION_REQUIRED",
                message=f"Upload of '{source_file.name}' requires user confirmation.",
                evidence={"file": str(source_file), "size": source_file.stat().st_size},
            )

        try:
            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await trigger_action()
            file_chooser: FileChooser = await fc_info.value
            await file_chooser.set_files(str(source_file))

            return InteractionOutcome(
                success=True,
                action="browser_upload",
                verification_status="VERIFIED",
                evidence={"file": str(source_file), "name": source_file.name},
                message=f"Uploaded '{source_file.name}' to file chooser.",
            )
        except Exception as e:
            logger.warning(f"File upload failed: {e}")
            return InteractionOutcome(
                success=False,
                action="browser_upload",
                verification_status="FAILED",
                failure_reason=BrowserFailureReason.UPLOAD_FAILED.value,
                message=str(e),
            )
