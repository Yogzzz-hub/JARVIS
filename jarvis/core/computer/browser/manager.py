"""Playwright Browser Lifecycle Manager with Dedicated Isolated Profile."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger("jarvis.computer.browser.manager")

DEFAULT_PROFILE_DIR = Path("data/browser/jarvis-profile").resolve()


class BrowserManager:
    """Manages Playwright lifecycle, dedicated profiles, persistent/ephemeral contexts, and recovery."""

    def __init__(self, profile_dir: Optional[Path] = None, headless: bool = True) -> None:
        self.profile_dir = profile_dir or DEFAULT_PROFILE_DIR
        self.headless = headless
        self._playwright: Optional[Any] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._active_page: Optional[Page] = None
        self._pages: Dict[str, Page] = {}
        self._is_running = False

    async def start(self) -> None:
        """Launch managed browser and create primary context with isolated profile."""
        if self._is_running and self._browser:
            return

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()

        # Launch Chromium with dedicated isolated user data dir
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            permissions=[],  # Deny extra permissions by default (camera, mic, notifications)
            viewport={"width": 1280, "height": 800},
            accept_downloads=True,
        )

        # Wire popup tracking
        self._context.on("page", self._on_new_page)

        # Get or create initial page
        pages = self._context.pages
        if pages:
            self._active_page = pages[0]
            self._pages["page_1"] = pages[0]
        else:
            self._active_page = await self._context.new_page()
            self._pages["page_1"] = self._active_page

        self._is_running = True
        logger.info(f"BrowserManager started with profile at {self.profile_dir}")

    def _on_new_page(self, page: Page) -> None:
        """Track new popup tabs automatically."""
        pid = f"page_{len(self._pages) + 1}"
        self._pages[pid] = page
        self._active_page = page
        logger.info(f"New browser page registered: {pid}")

    async def get_active_page(self) -> Page:
        """Return the current active page, starting browser if needed."""
        if not self._is_running or not self._active_page:
            await self.start()
        return self._active_page

    async def create_ephemeral_context(self) -> BrowserContext:
        """Create a transient private context for disposable research."""
        if not self._playwright:
            await self.start()
        browser = await self._playwright.chromium.launch(headless=self.headless)
        return await browser.new_context(permissions=[])

    async def recover_if_crashed(self) -> bool:
        """Detect browser process loss and restart managed session."""
        try:
            if self._active_page:
                await self._active_page.title()
                return True
        except Exception:
            logger.warning("Browser crash detected. Re-initiating session...")

        await self.stop()
        await self.start()
        return True

    async def stop(self) -> None:
        """Shut down browser contexts and Playwright cleanly."""
        try:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.debug(f"Error during browser shutdown: {e}")
        finally:
            self._context = None
            self._playwright = None
            self._active_page = None
            self._pages.clear()
            self._is_running = False
