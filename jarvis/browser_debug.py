"""Read-Only Browser Debug Inspector."""
from __future__ import annotations

import argparse
import asyncio
from jarvis.core.computer.browser.manager import BrowserManager
from jarvis.core.computer.browser.pages import BrowserNavigator
from jarvis.core.computer.browser.snapshot import BrowserSnapshotBuilder


async def run_debug(url: str | None = None) -> None:
    mgr = BrowserManager(headless=True)
    nav = BrowserNavigator(mgr)
    try:
        if url:
            print(f"Navigating to: {url}")
            try:
                await nav.navigate(url)
            except Exception as e:
                print(f"Navigation warning: Could not connect to {url} ({e})")

        page = await mgr.get_active_page()
        tabs = await nav.list_tabs()
        print("\nActive Browser Tabs:")
        for t in tabs:
            active_marker = " [ACTIVE]" if t["is_active"] else ""
            print(f"  [{t['page_id']}] '{t['title']}' -> {t['url']}{active_marker}")

        snap = await BrowserSnapshotBuilder.capture(page)
        print(f"\nSnapshot: '{snap.window_title}' ({snap.url})")
        print(f"Interactive Elements ({len(snap.elements)}):")
        for e in snap.elements:
            val_str = f" = '{e.value_summary}'" if e.value_summary else ""
            print(f"  - [{e.element_id}] {e.role} '{e.name}'{val_str} (id: '{e.automation_id}')")

        if snap.quarantine_notes:
            print("\nSecurity / Quarantine Notes:")
            for note in snap.quarantine_notes:
                print(f"  [!] {note}")
    finally:
        await mgr.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Browser Debug Inspector")
    parser.add_argument("--url", "-u", type=str, default=None, help="URL to inspect")
    args = parser.parse_args()
    asyncio.run(run_debug(args.url))


if __name__ == "__main__":
    main()
