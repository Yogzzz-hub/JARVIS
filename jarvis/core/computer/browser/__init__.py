"""Playwright Browser Automation Subsystem."""
from jarvis.core.computer.browser.manager import BrowserManager
from jarvis.core.computer.browser.pages import BrowserNavigator
from jarvis.core.computer.browser.snapshot import BrowserSnapshotBuilder
from jarvis.core.computer.browser.locator import BrowserLocatorResolver
from jarvis.core.computer.browser.actions import BrowserActionRunner
from jarvis.core.computer.browser.downloads import BrowserDownloadHandler
from jarvis.core.computer.browser.uploads import BrowserUploadHandler
from jarvis.core.computer.browser.security import detect_web_prompt_injection

__all__ = [
    "BrowserManager",
    "BrowserNavigator",
    "BrowserSnapshotBuilder",
    "BrowserLocatorResolver",
    "BrowserActionRunner",
    "BrowserDownloadHandler",
    "BrowserUploadHandler",
    "detect_web_prompt_injection",
]
