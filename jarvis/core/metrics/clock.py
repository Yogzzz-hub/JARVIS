from dataclasses import dataclass, field
from time import perf_counter_ns

now_ns = perf_counter_ns

@dataclass(slots=True)
class Clock:
    received_ns: int = field(default_factory=now_ns)
    parsed_ns: int = 0
    resolved_ns: int = 0
    lookup_ns: int = 0
    dispatch_started_ns: int = 0
    tool_started_ns: int = 0
    tool_returned_ns: int = 0
    verification_started_ns: int = 0
    verification_finished_ns: int = 0
    response_ready_ns: int = 0

    def metrics(self) -> dict[str, float | None]:
        def elapsed(a, b):
            return max(0, b - a) / 1e6 if a and b else None
        return {
            "gateway_parse_ms": elapsed(self.received_ns, self.parsed_ns),
            "command_resolution_ms": elapsed(self.parsed_ns, self.resolved_ns),
            "registry_lookup_ms": elapsed(self.resolved_ns, self.lookup_ns),
            "dispatch_ms": elapsed(self.dispatch_started_ns, self.tool_started_ns),
            "first_action_ms": elapsed(self.received_ns, self.tool_started_ns),
            "tool_return_ms": elapsed(self.tool_started_ns, self.tool_returned_ns),
            "verification_ms": elapsed(self.verification_started_ns, self.verification_finished_ns),
            "total_ms": elapsed(self.received_ns, self.response_ready_ns),
        }
