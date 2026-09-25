import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from jarvis.core.metrics.clock import Clock, now_ns

class State(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    UNDERSTANDING = "UNDERSTANDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RESPONDING = "RESPONDING"
    CANCELLED = "CANCELLED"

TRANSITIONS = {
    State.IDLE: {State.LISTENING, State.UNDERSTANDING, State.CANCELLED},
    State.LISTENING: {State.UNDERSTANDING, State.CANCELLED},
    State.UNDERSTANDING: {State.ACKNOWLEDGED, State.EXECUTING, State.FAILED, State.CANCELLED},
    State.ACKNOWLEDGED: {State.PLANNING, State.EXECUTING, State.FAILED, State.CANCELLED},
    State.PLANNING: {State.EXECUTING, State.FAILED, State.CANCELLED},
    State.EXECUTING: {State.VERIFYING, State.WAITING_CONFIRMATION, State.FAILED, State.CANCELLED},
    State.VERIFYING: {State.SUCCESS, State.FAILED, State.CANCELLED},
    State.WAITING_CONFIRMATION: {State.EXECUTING, State.RESPONDING, State.FAILED, State.CANCELLED},
    State.SUCCESS: {State.RESPONDING}, State.FAILED: {State.RESPONDING},
    State.CANCELLED: {State.RESPONDING}, State.RESPONDING: set(),
}

@dataclass(slots=True)
class Task:
    request_id: str
    source: str
    raw_text: str
    clock: Clock
    state: State = State.IDLE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timestamps: dict = field(default_factory=dict)
    result: object = None
    cancellation: asyncio.Event = field(default_factory=asyncio.Event)

    def snapshot(self):
        return {"request_id": self.request_id, "source": self.source, "raw_text": self.raw_text,
                "state": self.state, "created_at": self.created_at, "timestamps": self.timestamps,
                "result": self.result.model_dump(mode="json") if self.result else None}

class TaskManager:
    def __init__(self, bus, writer, capacity=512):
        self.tasks = OrderedDict()
        self.bus, self.writer, self.capacity = bus, writer, capacity

    def create(self, request, clock):
        if request.request_id in self.tasks:
            raise ValueError("duplicate request_id")
        while len(self.tasks) >= self.capacity:
            completed = next((key for key, t in self.tasks.items() if t.result is not None), None)
            if completed is None:
                raise RuntimeError("active task capacity reached")
            del self.tasks[completed]
        task = Task(request.request_id, request.source, request.text, clock)
        task.timestamps[State.IDLE] = now_ns()
        self.tasks[task.request_id] = task
        return task

    def transition(self, task, state):
        if state not in TRANSITIONS[task.state]:
            raise RuntimeError(f"illegal transition {task.state} -> {state}")
        task.state = state
        stamp = now_ns()
        task.timestamps[state] = stamp
        self.bus.emit("task.state_changed", task.request_id, state=state.value)
        self.writer.enqueue("task_events", task.request_id, {"state": state.value, "at_ns": stamp})

    def get(self, request_id):
        return self.tasks.get(request_id)

    def recent(self, limit=20):
        return tuple(reversed(tuple(self.tasks.values())))[:limit]

    def cancel(self, request_id):
        task = self.tasks[request_id]
        if State.CANCELLED in TRANSITIONS[task.state]:
            task.cancellation.set()
            return True
        return False
