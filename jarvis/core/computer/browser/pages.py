"""Browser Navigation, Tab Tracking, and Origin Management."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from playwright.async_api import Page
from jarvis.core.computer.browser.manager import BrowserManager

logger = logging.getLogger("jarvis.computer.browser.pages")


class BrowserNavigator:
    """Handles high-level navigation, origin change tracking, and tab switching."""

    def __init__(self, manager: BrowserManager) -> None:
        self.manager = manager

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate active page to specified URL with redirect/origin monitoring."""
        page = await self.manager.get_active_page()
        req_origin = urlparse(url).netloc

        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        status_code = response.status if response else 200
        final_url = page.url
        final_origin = urlparse(final_url).netloc
        title = await page.title()

        origin_changed = bool(req_origin and final_origin and req_origin != final_origin)

        return {
            "success": True,
            "url": final_url,
            "title": title,
            "status_code": status_code,
            "origin_changed": origin_changed,
            "requested_origin": req_origin,
            "final_origin": final_origin,
        }

    async def back(self) -> bool:
        page = await self.manager.get_active_page()
        await page.go_back(wait_until="domcontentloaded")
        return True

    async def forward(self) -> bool:
        page = await self.manager.get_active_page()
        await page.go_forward(wait_until="domcontentloaded")
        return True

    async def reload(self) -> bool:
        page = await self.manager.get_active_page()
        await page.reload(wait_until="domcontentloaded")
        return True

    async def list_tabs(self) -> List[Dict[str, Any]]:
        """List all active tabs in the current browser context."""
        await self.manager.get_active_page()
        tabs = []
        for pid, page in self.manager._pages.items():
            try:
                title = await page.title()
                tabs.append({
                    "page_id": pid,
                    "url": page.url,
                    "title": title,
                    "is_active": (page == self.manager._active_page),
                })
            except Exception:
                pass
        return tabs

    async def switch_tab(self, page_id: str) -> bool:
        """Switch active page pointer to specified tab."""
        if page_id in self.manager._pages:
            self.manager._active_page = self.manager._pages[page_id]
            await self.manager._active_page.bring_to_front()
            return True
        return False

    async def close_tab(self, page_id: str) -> bool:
        """Close specified tab."""
        if page_id in self.manager._pages:
            page = self.manager._pages.pop(page_id)
            await page.close()
            # Reset active page if needed
            if self.manager._active_page == page and self.manager._pages:
                self.manager._active_page = next(iter(self.manager._pages.values()))
            return True
        return False
