"""Read-Only Desktop UI Inspector."""
from __future__ import annotations

import argparse
import sys
from jarvis.core.computer.windows.backend import WindowsUIABackend
from jarvis.core.computer.windows.snapshot import UIASnapshotBuilder
from jarvis.core.computer.windows.windows import WindowManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Windows UIA Tree Inspector")
    parser.add_argument("--window", "-w", type=str, default=None, help="Target window title or ID")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Maximum windows or elements to display")
    args = parser.parse_args()

    backend = WindowsUIABackend()
    wm = WindowManager(backend)

    if not args.window:
        print("\nActive Windows:")
        windows = wm.list_windows(limit=args.limit)
        for w in windows:
            fg = " [FOREGROUND]" if w.get("foreground") else ""
            print(f"  [{w['window_id']}] PID: {w['process_id']} | '{w['window_title']}'{fg}")
        print("\nPass --window <ID or Title> to inspect its structured UIA tree.")
        return

    win, status = wm.resolve_target_window(args.window)
    if not win:
        print(f"Window '{args.window}' resolution status: {status}")
        return

    print(f"\nInspecting Window: [{win['window_id']}] '{win['window_title']}'")
    builder = UIASnapshotBuilder(backend)
    snap = builder.capture_snapshot(win["window_id"], max_elements=args.limit)

    print(f"Total Structured Elements: {len(snap.elements)}\n")
    for e in snap.elements:
        actions_str = ", ".join(e.actions_supported) if e.actions_supported else "none"
        auto_id_str = f" | ID: '{e.automation_id}'" if e.automation_id else ""
        print(f"  - [{e.element_id}] {e.control_type}: '{e.name}'{auto_id_str} | Patterns: [{actions_str}]")


if __name__ == "__main__":
    main()
