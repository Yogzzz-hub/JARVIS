from __future__ import annotations

import sys
from jarvis.connectors.manager import ConnectorManager


def print_connectors_status() -> int:
    mgr = ConnectorManager.get_default()
    statuses = mgr.get_all_statuses(force_refresh=True)

    print("\n========================================================")
    print("                JARVIS EDGE CONNECTORS")
    print("========================================================\n")
    print(f"{'CONNECTOR':<18} {'STATUS':<14} {'DETAILS'}")
    print(f"{'-'*16:<18} {'-'*12:<14} {'-'*30}")

    for name, s in statuses.items():
        st = s.get("status", "UNKNOWN")
        msg = s.get("message", "")
        print(f"{name.capitalize():<18} {st:<14} {msg}")

    print("\n========================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(print_connectors_status())
