"""CLI tool for managing and inspecting JARVIS Approved Workflows (Phase 12)."""

import argparse
import sys
from pathlib import Path
from jarvis.config import ROOT
from jarvis.core.workflows.library import WorkflowLibrary


def get_library() -> WorkflowLibrary:
    db_file = ROOT / "db/jarvis.db"
    if not db_file.exists():
        db_file = ROOT.parent / "db/jarvis.db"
    return WorkflowLibrary(db_file)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Approved Workflows Management CLI")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # list
    subparsers.add_parser("list", help="List approved workflows")

    # inspect
    inspect_p = subparsers.add_parser("inspect", help="Inspect a specific workflow by ID")
    inspect_p.add_argument("workflow_id", help="Workflow ID")

    # disable
    disable_p = subparsers.add_parser("disable", help="Disable a specific workflow by ID")
    disable_p.add_argument("workflow_id", help="Workflow ID to disable")

    # delete
    delete_p = subparsers.add_parser("delete", help="Delete a specific workflow by ID")
    delete_p.add_argument("workflow_id", help="Workflow ID to delete")

    # candidates
    subparsers.add_parser("candidates", help="Show proposed workflow candidates")

    args = parser.parse_args()
    lib = get_library()

    if args.action == "list":
        wfs = lib.list_workflows()
        print("============================================================")
        print("               JARVIS APPROVED WORKFLOWS")
        print("============================================================")
        print(f"Total Approved Workflows: {len(wfs)}\n")
        for wf in wfs:
            print(f"ID:          {wf.workflow_id}")
            print(f"Name:        {wf.name}")
            print(f"Description: {wf.description}")
            print(f"Status:      {wf.status.value}")
            print(f"Risk:        {wf.risk_profile}")
            print(f"Runs:        {wf.success_count + wf.failure_count} (Successes: {wf.success_count}, Failures: {wf.failure_count})")
            print(f"Tools:       {', '.join(wf.required_tools)}")
            print("------------------------------------------------------------")
        print("============================================================")

    elif args.action == "inspect":
        wfs = [w for w in lib.list_workflows() if w.workflow_id == args.workflow_id]
        if not wfs:
            print(f"Workflow '{args.workflow_id}' not found.", file=sys.stderr)
            return 1
        wf = wfs[0]
        print("============================================================")
        print(f"JARVIS Workflow Inspector -- {wf.name}")
        print("============================================================")
        print(f"ID:             {wf.workflow_id}")
        print(f"Name:           {wf.name}")
        print(f"Description:    {wf.description}")
        print(f"Status:         {wf.status.value}")
        print(f"Risk Profile:   {wf.risk_profile}")
        print(f"Schema Version: {wf.schema_version}")
        print(f"Fingerprint:    {wf.registry_fingerprint}")
        print(f"Inputs:         {[s.name + ':' + s.slot_type for s in wf.input_schema]}")
        print(f"Nodes ({len(wf.graph_template.nodes)}):")
        for n in wf.graph_template.nodes:
            print(f"  - [{n.node_template_id}] {n.tool} (risk={n.risk}, deps={n.depends_on})")
        print(f"Success Count:  {wf.success_count}")
        print(f"Failure Count:  {wf.failure_count}")
        print(f"Avg Latency:    {wf.avg_latency_ms:.2f} ms")
        print("============================================================")

    elif args.action == "disable":
        success = lib.disable_workflow(args.workflow_id)
        if success:
            print(f"Workflow '{args.workflow_id}' disabled.")
        else:
            print(f"Failed to disable workflow '{args.workflow_id}'.", file=sys.stderr)
            return 1

    elif args.action == "delete":
        success = lib.delete_workflow(args.workflow_id)
        if success:
            print(f"Workflow '{args.workflow_id}' deleted.")
        else:
            print(f"Failed to delete workflow '{args.workflow_id}'.", file=sys.stderr)
            return 1

    elif args.action == "candidates":
        print("============================================================")
        print("               JARVIS WORKFLOW CANDIDATES")
        print("============================================================")
        print("Proposed Candidates: 0 (Proposals require >= 3 verified runs)")
        print("============================================================")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
