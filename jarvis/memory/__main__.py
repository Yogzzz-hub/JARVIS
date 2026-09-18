"""CLI tool for managing and inspecting JARVIS Memory (Phase 12)."""

import argparse
import sys
from pathlib import Path
from jarvis.config import ROOT
from jarvis.core.memory.store import SQLiteMemoryStore


def get_store() -> SQLiteMemoryStore:
    db_file = ROOT / "db/jarvis.db"
    if not db_file.exists():
        db_file = ROOT.parent / "db/jarvis.db"
    return SQLiteMemoryStore(db_file)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Local Memory Management CLI")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # list
    list_p = subparsers.add_parser("list", help="List active memories")
    list_p.add_argument("--layer", choices=["SESSION", "WORKING", "EPISODIC", "SEMANTIC", "PREFERENCE", "WORKFLOW"], help="Filter by layer")
    list_p.add_argument("--limit", type=int, default=20, help="Maximum number of items")

    # inspect
    inspect_p = subparsers.add_parser("inspect", help="Inspect a specific memory by ID")
    inspect_p.add_argument("memory_id", help="Memory ID")

    # forget
    forget_p = subparsers.add_parser("forget", help="Delete a specific memory by ID")
    forget_p.add_argument("memory_id", help="Memory ID to delete")

    # conflicts
    subparsers.add_parser("conflicts", help="Show superseded or conflicting memories")

    args = parser.parse_args()
    store = get_store()

    if args.action == "list":
        items = store.list_active(limit=args.limit)
        print("============================================================")
        print("                 JARVIS ACTIVE MEMORIES")
        print("============================================================")
        print(f"Total Active Items: {len(items)}\n")
        for item in items:
            print(f"ID:         {item.memory_id}")
            print(f"Layer:      {item.layer.value} | Kind: {item.kind}")
            print(f"Key:        {item.key}")
            print(f"Value:      {item.value}")
            print(f"Source:     {item.provenance.source_type.value} ({item.confidence.value})")
            print(f"Used Count: {item.use_count} (Success: {item.successful_use_count})")
            print("------------------------------------------------------------")
        print("============================================================")

    elif args.action == "inspect":
        item = store.get_by_id(args.memory_id)
        if not item:
            print(f"Memory with ID '{args.memory_id}' not found.", file=sys.stderr)
            return 1
        print("============================================================")
        print(f"JARVIS Memory Inspector -- {item.memory_id}")
        print("============================================================")
        print(f"Layer:          {item.layer.value}")
        print(f"Kind:           {item.kind}")
        print(f"Key:            {item.key}")
        print(f"Value:          {item.value}")
        print(f"Status:         {item.status.value}")
        print(f"Confidence:     {item.confidence.value}")
        print(f"Source Type:    {item.provenance.source_type.value}")
        print(f"Source Ref:     {item.provenance.source_reference or 'None'}")
        print(f"Supersedes ID:  {item.provenance.supersedes_id or 'None'}")
        print(f"Created At:     {item.created_at}")
        print(f"Expires At:     {item.expires_at or 'Never'}")
        print("============================================================")

    elif args.action == "forget":
        success = store.delete(args.memory_id)
        if success:
            print(f"Memory '{args.memory_id}' permanently forgotten from local database.")
        else:
            print(f"Failed to delete memory '{args.memory_id}'.", file=sys.stderr)
            return 1

    elif args.action == "conflicts":
        stats = store.get_stats()
        print("============================================================")
        print("                 JARVIS MEMORY CONFLICTS")
        print("============================================================")
        print(f"Active Memories:     {stats['active_memories']}")
        print(f"Superseded Memories: {stats['superseded_memories']}")
        print(f"Expired Memories:    {stats['expired_memories']}")
        print("============================================================")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
