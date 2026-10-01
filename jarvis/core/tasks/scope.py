"""TaskScopeManager: a task may only use the capabilities it was granted for *this* request.

The local model (planner / agent) never gets the whole tool registry. For every command the service grants the
capabilities the route or the validated plan needs; the executor refuses any other tool while that grant is
active; the grant is revoked when the command's single final response is produced.

    with scopes.grant(task_id, {"window_op", "text_op"}, reason="compound route"):
        await executor.execute(...)          # anything else -> PermissionError

Grants travel with asyncio context (contextvars), so steps run by the DAG scheduler or the agent loop inside the
command inherit them. Code that runs outside any command (watchers re-dispatch through the service, which grants
afresh) has no active grant.
"""
from __future__ import annotations

import contextlib
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterable, Optional

# Always allowed inside a grant: reading JARVIS's own state never touches the PC, phone or the outside world.
ALWAYS = frozenset({"task_status", "previous_outcome", "recent_actions", "jarvis_availability", "get_time"})


@dataclass
class Grant:
    task_id: str
    tools: set[str]
    reason: str = ""
    created: float = field(default_factory=time.time)
    used: list[str] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)
    revoked: bool = False

    def allows(self, tool: str) -> bool:
        return not self.revoked and (tool in self.tools or tool in ALWAYS)


_CURRENT: ContextVar[Optional[Grant]] = ContextVar("jarvis_task_grant", default=None)


class ScopeDenied(PermissionError):
    pass


class TaskScopeManager:
    def __init__(self, history: int = 200):
        self._active: dict[str, Grant] = {}
        self._history: list[Grant] = []
        self._size = history
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def grant(self, task_id: str, tools: Iterable[str], reason: str = ""):
        g = Grant(task_id=task_id, tools={t for t in tools if t}, reason=reason)
        outer = _CURRENT.get()
        if outer is not None and not outer.revoked:
            g.tools &= outer.tools | ALWAYS        # a nested grant can only narrow, never widen
        with self._lock:
            self._active[task_id] = g
        token = _CURRENT.set(g)
        try:
            yield g
        finally:
            _CURRENT.reset(token)
            self.revoke(task_id)

    def narrow(self, tools: Iterable[str]) -> None:
        """The agent picked its working set: the current grant shrinks to it (never grows)."""
        g = _CURRENT.get()
        if g is not None:
            g.tools &= set(tools) | ALWAYS

    def extend(self, tools: Iterable[str], reason: str = "") -> None:
        """Only for the service: a validated plan or an approved step adds exactly its own tools."""
        g = _CURRENT.get()
        if g is not None:
            g.tools |= set(tools)
            if reason:
                g.reason = f"{g.reason}; {reason}".strip("; ")

    def check(self, tool: str) -> None:
        g = _CURRENT.get()
        if g is None:
            return
        if not g.allows(tool):
            g.denied.append(tool)
            raise ScopeDenied(f"'{tool}' is not part of what this task was allowed to do "
                              f"(granted: {', '.join(sorted(g.tools)) or 'nothing'}).")
        g.used.append(tool)

    def revoke(self, task_id: str) -> None:
        with self._lock:
            g = self._active.pop(task_id, None)
            if g is not None:
                g.revoked = True
                self._history = [g] + self._history[: self._size - 1]

    def current(self) -> Optional[Grant]:
        return _CURRENT.get()

    def active(self) -> list[Grant]:
        with self._lock:
            return list(self._active.values())

    def recent(self, n: int = 10) -> list[Grant]:
        with self._lock:
            return self._history[:n]


_mgr: Optional[TaskScopeManager] = None


def get_scope_manager() -> TaskScopeManager:
    global _mgr
    if _mgr is None:
        _mgr = TaskScopeManager()
    return _mgr
