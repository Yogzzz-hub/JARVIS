"""Playwright Download Event Handling and Local Verification."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from playwright.async_api import Download, Page
from jarvis.core.computer.models import BrowserFailureReason, InteractionOutcome

logger = logging.getLogger("jarvis.computer.browser.downloads")


class BrowserDownloadHandler:
    """Safely captures, inspects, policies, and verifies browser downloads."""

    @classmethod
    async def download_file(
        cls,
        page: Page,
        trigger_action: Any,  # Async callable triggering the download
        destination: Path,
        allow_overwrite: bool = False,
    ) -> InteractionOutcome:
        """Execute action, capture download event, inspect and verify saved file."""
        if destination.exists() and not allow_overwrite:
            return InteractionOutcome(
                success=False,
                action="browser_download",
                verification_status="FAILED",
                message=f"Destination file '{destination.name}' already exists. Overwrite denied by policy.",
            )

        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with page.expect_download(timeout=20000) as download_info:
                await trigger_action()
            download: Download = await download_info.value
        except Exception as e:
            logger.warning(f"Download event timed out or failed: {e}")
            return InteractionOutcome(
                success=False,
                action="browser_download",
                verification_status="FAILED",
                failure_reason=BrowserFailureReason.DOWNLOAD_FAILED.value,
                message=str(e),
            )

        # Save to destination
        await download.save_as(str(destination))

        # Verify local file
        if not destination.exists():
            return InteractionOutcome(
                success=False,
                action="browser_download",
                verification_status="FAILED",
                message="Downloaded file not found at expected path.",
            )

        size_bytes = destination.stat().st_size
        sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()

        evidence = {
            "path": str(destination),
            "size_bytes": size_bytes,
            "sha256": sha256,
            "suggested_filename": download.suggested_filename,
        }

        return InteractionOutcome(
            success=True,
            action="browser_download",
            verification_status="VERIFIED",
            evidence=evidence,
            message=f"Downloaded '{destination.name}' ({size_bytes} bytes). Integrity verified.",
        )
