from __future__ import annotations

import asyncio
import os
import signal
import sys
from enum import StrEnum
from typing import Any

class CancellationState(StrEnum):
    CANCELLED_BEFORE_START = "CANCELLED_BEFORE_START"
    CANCELLED_DURING_EXECUTION = "CANCELLED_DURING_EXECUTION"
    COMPLETED_BEFORE_CANCEL = "COMPLETED_BEFORE_CANCEL"
    NOT_CANCELLABLE = "NOT_CANCELLABLE"

class ExecutionSupervisor:
    """Global execution supervisor providing high-priority kill-switch control
    and child process lifecycle management.
    """

    def __init__(self) -> None:
        self._global_stop = asyncio.Event()
        self._cancelled_graphs: set[str] = set()
        self._cancelled_nodes: set[str] = set()
        self._tracked_processes: dict[str, Any] = {}

    def is_stopped(self) -> bool:
        return self._global_stop.is_set()

    def is_graph_cancelled(self, graph_id: str) -> bool:
        return self._global_stop.is_set() or graph_id in self._cancelled_graphs

    def is_node_cancelled(self, node_id: str) -> bool:
        return self._global_stop.is_set() or node_id in self._cancelled_nodes

    def stop_all(self) -> None:
        """Trigger global emergency stop immediately."""
        self._global_stop.set()
        self.terminate_tracked_processes()

    def cancel_graph(self, graph_id: str) -> None:
        self._cancelled_graphs.add(graph_id)

    def cancel_node(self, node_id: str) -> None:
        self._cancelled_nodes.add(node_id)

    def register_process(self, task_id: str, proc: Any) -> None:
        self._tracked_processes[task_id] = proc

    def unregister_process(self, task_id: str) -> None:
        self._tracked_processes.pop(task_id, None)

    def terminate_tracked_processes(self) -> None:
        for task_id, proc in list(self._tracked_processes.items()):
            try:
                if hasattr(proc, "terminate"):
                    proc.terminate()
                elif hasattr(proc, "kill"):
                    proc.kill()
            except Exception:
                pass
        self._tracked_processes.clear()

    def reset(self) -> None:
        self._global_stop.clear()
        self._cancelled_graphs.clear()
        self._cancelled_nodes.clear()
        self._tracked_processes.clear()

# Global supervisor singleton
global_supervisor = ExecutionSupervisor()
