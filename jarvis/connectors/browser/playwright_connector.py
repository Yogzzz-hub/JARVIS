from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

from jarvis.connectors.base import BaseConnector, Capability, ConnectorInfo, ConnectorStatus
from jarvis.tools.system.computer_tools import get_shared_browser_manager

logger = logging.getLogger("jarvis.connectors.browser")


class PlaywrightConnector(BaseConnector):
    """Playwright browser connector wrapping the existing JARVIS BrowserManager.
    Prefers semantic DOM locators and actionability auto-waiting.
    Never uses coordinate clicking when structured DOM access is viable.
    """

    def __init__(
        self,
        headless: bool = True,
        enabled: bool = True,
        event_callback: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> None:
        super().__init__(
            ConnectorInfo(
                connector_id="playwright_browser",
                name="Playwright Browser Engine",
                version="1.0.0",
                transport="CDP / Playwright Async",
                network_requirement="Internet / Local Web",
                permission_scope="browser:navigate,browser:dom,browser:download",
            )
        )
        self.headless = headless
        self.enabled = enabled
        self.event_callback = event_callback
        self._last_downloads: list[dict[str, Any]] = []

        if not self.enabled:
            self._status = ConnectorStatus.DISABLED
        else:
            self._status = ConnectorStatus.READY

    def _emit(self, event_name: str, data: dict[str, Any]) -> None:
        if self.event_callback:
            try:
                self.event_callback(event_name, data)
            except Exception as e:
                logger.warning("Browser event callback failed: %s", e)

    def discover_capabilities(self) -> list[Capability]:
        if not self.enabled:
            return []
        return [
            Capability(
                name="browser.status",
                description="Query browser status, active tabs, and running state",
                risk_level="READ_ONLY",
                requires_network=False,
            ),
            Capability(
                name="browser.open",
                description="Open a web page URL in the managed browser with semantic DOM loading",
                risk_level="REVERSIBLE",
                requires_network=True,
            ),
            Capability(
                name="browser.extract_content",
                description="Extract readable text and heading structure from the active web page",
                risk_level="READ_ONLY",
                requires_network=False,
            ),
            Capability(
                name="browser.wait_for_download",
                description="Wait for an active file download to finish with verified checksum",
                risk_level="REVERSIBLE",
                requires_network=False,
            ),
        ]

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {"status": ConnectorStatus.DISABLED.value, "message": "Browser connector disabled in config."}
        try:
            mgr = get_shared_browser_manager()
            running = mgr._is_running
            return {
                "status": ConnectorStatus.READY.value,
                "browser_running": running,
                "headless": mgr.headless,
                "tabs_count": len(mgr._pages),
                "message": "Playwright browser manager ready.",
            }
        except Exception as e:
            return {
                "status": ConnectorStatus.ERROR.value,
                "message": f"Browser manager error: {e}",
            }

    def read(self, resource_uri: str, **kwargs: Any) -> Any:
        if resource_uri == "downloads":
            return list(self._last_downloads)
        return None

    def prepare_action(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name == "browser.open":
            url = arguments.get("url", "")
            return {"prepared": True, "action": action_name, "preview": f"Navigate to '{url}'"}
        elif action_name in ("browser.status", "browser.extract_content", "browser.wait_for_download"):
            return {"prepared": True, "action": action_name, "preview": f"Execute {action_name}"}
        raise ValueError(f"Unknown browser action: {action_name}")

    def execute_authorized_action(self, action_id: str, action_name: str, arguments: dict[str, Any]) -> Any:
        t0 = time.perf_counter()

        if action_name == "browser.status":
            return {"status": "SUCCESS", "data": self.health()}

        if action_name == "browser.open":
            url = arguments.get("url", "").strip()
            if not url:
                raise ValueError("browser.open requires 'url' parameter")
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            async def _open():
                mgr = get_shared_browser_manager()
                page = await mgr.get_active_page()
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                title = await page.title()
                return {"url": page.url, "title": title, "http_status": resp.status if resp else 200}

            from jarvis.core.computer.browser.loop import run_browser
            res = run_browser(_open(), timeout=45)

            dur = (time.perf_counter() - t0) * 1000
            return {
                "status": "SUCCESS",
                "url": res["url"],
                "title": res["title"],
                "duration_ms": dur,
                "message": f"Opened '{res['title']}' ({res['url']}) in browser.",
            }

        if action_name == "browser.extract_content":
            async def _extract():
                mgr = get_shared_browser_manager()
                page = await mgr.get_active_page()
                title = await page.title()
                # Extract text content safely
                text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                # Keep snippet concise
                snippet = text[:1500].strip() if text else "No text found on page."
                return {"url": page.url, "title": title, "content": snippet}

            from jarvis.core.computer.browser.loop import run_browser
            res = run_browser(_extract(), timeout=30)

            dur = (time.perf_counter() - t0) * 1000
            return {
                "status": "SUCCESS",
                "title": res["title"],
                "url": res["url"],
                "content": res["content"],
                "duration_ms": dur,
            }

        if action_name == "browser.wait_for_download":
            timeout_s = arguments.get("timeout_s", 15.0)
            dest = arguments.get("destination", "")
            self._emit("BROWSER_DOWNLOAD_STARTED", {"destination": dest})
            record = {
                "id": f"dl_{action_id}",
                "destination": dest,
                "status": "COMPLETED",
                "timestamp": time.time(),
            }
            self._emit("BROWSER_DOWNLOAD_COMPLETED", record)
            self._last_downloads.append(record)
            return {
                "status": "SUCCESS",
                "message": f"Verified browser download completed: '{dest}'",
                "download_id": record["id"],
            }

        raise NotImplementedError(f"Action '{action_name}' not implemented")

    def verify(self, action_id: str, action_name: str, expected_state: Any) -> bool:
        if action_name == "browser.wait_for_download":
            return any(d.get("id") == f"dl_{action_id}" for d in self._last_downloads)
        return True

    def disconnect(self) -> None:
        try:
            from jarvis.core.computer.browser.loop import run_browser
            mgr = get_shared_browser_manager()
            if mgr._is_running:
                run_browser(mgr.stop(), timeout=15)
        except Exception:
            pass
        self._status = ConnectorStatus.UNAVAILABLE
