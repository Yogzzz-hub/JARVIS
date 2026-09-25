"""Context Assembler building bounded ContextPackets with strict token budgets (Phase 12)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from jarvis.core.context.models import (
    ContextPacket,
    OperationalMode,
    ProjectContext,
    ReferenceConfidence,
    ReferenceResolution,
)
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.memory.models import MemoryItem, MemoryQuery

if TYPE_CHECKING:
    from jarvis.core.memory.store import SQLiteMemoryStore
    from jarvis.core.memory.working import BoundedWorkingMemory


MAX_CONTEXT_TOKENS = 512


class ContextAssembler:
    """
    Assembles unified ContextPackets for router, planner, and specialist coordination.
    Enforces a strict token budget and provides a sub-millisecond fast-path for
    deterministic commands without disk or model lookups.
    """

    def __init__(
        self,
        working_memory: BoundedWorkingMemory,
        memory_store: Optional[SQLiteMemoryStore] = None,
        resolver: Optional[ReferenceResolver] = None,
        current_mode: OperationalMode = OperationalMode.DEFAULT,
    ):
        self.working_memory = working_memory
        self.memory_store = memory_store
        self.resolver = resolver or ReferenceResolver(working_memory, memory_store)
        self.current_mode = current_mode
        self._cross_device_context: Dict[str, Any] = {}

    def set_mode(self, mode: OperationalMode):
        self.current_mode = mode

    def record_cross_device_event(self, device_id: str, data: Dict[str, Any]):
        """Records task state received from Android phone or remote client."""
        self._cross_device_context[device_id] = {
            "timestamp": time.time(),
            "data": data,
        }
        if "file_path" in data:
            self.working_memory.record_file_opened(data["file_path"])
        if "folder_path" in data:
            self.working_memory.record_folder_selected(data["folder_path"])

    def assemble(
        self,
        utterance: str,
        is_deterministic_hint: bool = False,
        is_consequential: bool = False,
    ) -> ContextPacket:
        """
        Assembles a bounded ContextPacket.
        If is_deterministic_hint is True, executes fast path (p95 < 1 ms).
        """
        t0 = time.perf_counter()
        working_snapshot = self.working_memory.snapshot()

        # Fast path for deterministic commands ("open chrome", "volume 30", "open calculator")
        simple_prefixes = ("open ", "launch ", "start ", "volume ", "set volume ", "mute", "unmute", "close ", "kill ")
        has_context_keywords = any(k in utterance.lower() for k in ("it", "that", "second", "third", "first", "yesterday", "again", "project", "same folder", "last"))
        if is_deterministic_hint or (any(utterance.lower().startswith(p) for p in simple_prefixes) and not has_context_keywords):
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return ContextPacket(
                request=utterance,
                working_context=working_snapshot,
                resolved_references={},
                relevant_memories=[],
                current_mode=self.current_mode,
                token_estimate=len(utterance.split()) + 10,
                explanation={"assembly_ms": elapsed_ms, "fast_path": True},
            )

        # 1. Resolve conversational references
        resolved_ref = self.resolver.resolve(utterance, is_consequential=is_consequential)
        resolved_dict = {}
        if resolved_ref.referent is not None or resolved_ref.clarification_prompt is not None:
            resolved_dict["primary"] = resolved_ref
        if getattr(resolved_ref, "resolved_entity", None):
            resolved_dict["entity"] = resolved_ref.resolved_entity
        if getattr(resolved_ref, "resolved_resource", None):
            resolved_dict["resource"] = resolved_ref.resolved_resource

        # 2. Retrieve relevant memories from SQLite store
        relevant_memories: List[MemoryItem] = []
        skip_memory_search = (
            resolved_ref.confidence == ReferenceConfidence.HIGH
            and resolved_ref.source in ("WORKING_MEMORY_LAST_FILE", "RECENT_SEARCH_ORDINAL", "SEARCH_ORDINAL", "RECENT_FILES_ORDINAL")
        )
        if self.memory_store is not None and not skip_memory_search:
            # Query relevant keywords extracted from utterance
            q = MemoryQuery(query_text=utterance, limit=5)
            query_results = self.memory_store.query(q)
            relevant_memories = [qr.item for qr in query_results]

        # 3. Active project context
        active_project = None
        proj_name = self.working_memory.get_current_project()
        if proj_name:
            active_project = ProjectContext(
                project_id=proj_name.lower().replace(" ", "_"),
                name=proj_name,
                recent_files=self.working_memory.get_recent_files()[:3],
            )

        # 4. Truncate and budget tokens
        token_estimate = len(utterance.split()) + len(working_snapshot) * 4
        budgeted_memories: List[MemoryItem] = []
        for mem in relevant_memories:
            item_tokens = len(mem.to_text_for_search().split())
            if token_estimate + item_tokens <= MAX_CONTEXT_TOKENS:
                budgeted_memories.append(mem)
                token_estimate += item_tokens
            else:
                break

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return ContextPacket(
            request=utterance,
            working_context=working_snapshot,
            resolved_references=resolved_dict,
            relevant_memories=budgeted_memories,
            active_project=active_project,
            current_mode=self.current_mode,
            token_estimate=token_estimate,
            explanation={"assembly_ms": elapsed_ms, "fast_path": False, "memories_considered": len(relevant_memories)},
        )
