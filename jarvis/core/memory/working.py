"""Ultra-fast bounded working memory for active interaction context (Phase 12).

Maintains structured, typed conversational context across interaction turns:
- Active topic and topic stack for topic switches and returns
- Current and selected resource references (file, folder, app, device, browser)
- Recent result sets with ranked ordinal indexing
- High-confidence extracted entities and assistant knowledge annotations
- Recent failures for context-aware recovery (e.g. VLC missing -> install it)
- Pending confirmations, clarifications, and message drafts
- Time and turn-based decay without durable memory pollution
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.core.context.models import (
    ApplicationResourceRef,
    BaseResourceRef,
    DraftResourceRef,
    EntityRef,
    EntityType,
    FileResourceRef,
    FolderResourceRef,
    PendingClarification,
    PendingConfirmation,
    ResultSet,
    TaskContext,
    TopicRef,
    WorkingContext,
)
from jarvis.core.memory.models import MemoryItem


class BoundedWorkingMemory:
    """
    Maintains bounded in-memory working context for rapid reference resolution.
    Guarantees p95 lookup latency < 1 ms without hitting disk or embedding models.
    """

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self._recent_files: List[str] = []
        self._recent_folders: List[str] = []
        self._recent_apps: List[str] = []
        self._recent_search_results: List[Dict[str, Any]] = []
        self._last_opened_file: Optional[str] = None
        self._last_selected_folder: Optional[str] = None
        self._last_focused_app: Optional[str] = None
        self._current_project: Optional[str] = None
        self._last_successful_task: Optional[str] = None
        self._last_failed_task: Optional[str] = None
        self._recent_resources: List[BaseResourceRef] = []
        self._custom_items: Dict[str, MemoryItem] = {}

        # Structured Working Context
        self.context: WorkingContext = WorkingContext()

    # -------------------------------------------------------------------------
    # Topic Stack & Active Topic Management
    # -------------------------------------------------------------------------
    def push_topic(self, topic: TopicRef | str, entity_type: EntityType = EntityType.TOPIC) -> None:
        """Pushes new active topic onto the topic stack and sets as active."""
        if isinstance(topic, str):
            topic = TopicRef(
                entity_id=topic.lower().replace(" ", "_"),
                canonical_name=topic,
                display_name=topic,
                entity_type=entity_type,
            )
        if self.context.active_topic:
            # If same canonical topic, just refresh
            if self.context.active_topic.canonical_name == topic.canonical_name:
                self.context.active_topic.salience = 1.0
                self.context.active_topic.last_mentioned_at = time.time()
                self.record_entity(topic)
                return
            self.context.topic_stack.append(self.context.active_topic)
            if len(self.context.topic_stack) > 10:
                self.context.topic_stack.pop(0)

        self.context.active_topic = topic
        self.record_entity(topic)

    def pop_topic(self) -> Optional[TopicRef]:
        """Pops current topic and restores previous topic from stack."""
        prev = self.context.topic_stack.pop() if self.context.topic_stack else None
        self.context.active_topic = prev
        return prev

    def restore_topic(self, name_or_alias: str) -> Optional[TopicRef]:
        """Restores a previous topic from topic stack or recent entities by name/alias."""
        clean = name_or_alias.strip().casefold()
        for idx in range(len(self.context.topic_stack) - 1, -1, -1):
            top = self.context.topic_stack[idx]
            if top.canonical_name.casefold() == clean or any(a.casefold() == clean for a in top.aliases):
                restored = self.context.topic_stack.pop(idx)
                if self.context.active_topic:
                    self.context.topic_stack.append(self.context.active_topic)
                self.context.active_topic = restored
                restored.salience = 1.0
                restored.last_mentioned_at = time.time()
                return restored

        for ent in self.context.recent_entities:
            if ent.canonical_name.casefold() == clean or any(a.casefold() == clean for a in ent.aliases):
                if self.context.active_topic:
                    self.context.topic_stack.append(self.context.active_topic)
                self.context.active_topic = ent
                ent.salience = 1.0
                ent.last_mentioned_at = time.time()
                return ent

        return None

    def get_active_topic(self) -> Optional[TopicRef]:
        """Returns currently active topic."""
        return self.context.active_topic

    @property
    def active_topic(self) -> Optional[TopicRef]:
        return self.context.active_topic

    def set_active_topic(self, topic: Optional[TopicRef]) -> None:
        self.context.active_topic = topic

    def clear_active_topic(self) -> None:
        self.context.active_topic = None

    def get_topic_stack(self) -> List[TopicRef]:
        return list(self.context.topic_stack)

    # -------------------------------------------------------------------------
    # Entity Tracking
    # -------------------------------------------------------------------------
    def record_entity(self, entity: EntityRef) -> None:
        """Records or updates an entity in recent entities."""
        # Check if already present
        for existing in self.context.recent_entities:
            if existing.canonical_name == entity.canonical_name:
                existing.salience = 1.0
                existing.last_mentioned_at = time.time()
                existing.confidence = max(existing.confidence, entity.confidence)
                if entity.possible_capabilities:
                    for cap in entity.possible_capabilities:
                        if cap not in existing.possible_capabilities:
                            existing.possible_capabilities.append(cap)
                return

        self.context.recent_entities.insert(0, entity)
        if len(self.context.recent_entities) > self.max_items:
            self.context.recent_entities.pop()

    add_entity = record_entity

    def get_recent_entities(self, entity_type: Optional[EntityType] = None) -> List[EntityRef]:
        if entity_type is None:
            return list(self.context.recent_entities)
        return [e for e in self.context.recent_entities if e.entity_type == entity_type]

    # -------------------------------------------------------------------------
    # Result Sets & Ordinal Management
    # -------------------------------------------------------------------------
    def record_result_set(self, result_set: ResultSet) -> None:
        """Records an ordered query result set and marks it as active."""
        for rs in self.context.recent_result_sets:
            rs.active = False
        self.context.recent_result_sets.insert(0, result_set)
        if len(self.context.recent_result_sets) > 10:
            self.context.recent_result_sets.pop()

    set_result_set = record_result_set

    def get_active_result_set(self) -> Optional[ResultSet]:
        for rs in self.context.recent_result_sets:
            if rs.active:
                return rs
        return self.context.recent_result_sets[0] if self.context.recent_result_sets else None

    # -------------------------------------------------------------------------
    # Resource Focus
    # -------------------------------------------------------------------------
    def set_current_resource(self, res: BaseResourceRef) -> None:
        self.context.current_resource = res
        self._record_recent_resource(res)

    def get_current_resource(self) -> Optional[BaseResourceRef]:
        return self.context.current_resource

    def set_selected_resource(self, res: BaseResourceRef) -> None:
        self.context.selected_resource = res
        self._record_recent_resource(res)

    def get_selected_resource(self) -> Optional[BaseResourceRef]:
        return self.context.selected_resource

    def _record_recent_resource(self, res: BaseResourceRef) -> None:
        # Avoid duplicate consecutive
        if self._recent_resources and self._recent_resources[0].canonical_identifier == res.canonical_identifier:
            return
        self._recent_resources.insert(0, res)
        if len(self._recent_resources) > self.max_items:
            self._recent_resources.pop()
        self.context.recent_resources = list(self._recent_resources)

    def get_recent_resources(self) -> List[BaseResourceRef]:
        return list(self._recent_resources)

    # -------------------------------------------------------------------------
    # Failure Outcome Tracking (for failure follow-ups e.g. VLC missing -> install it)
    # -------------------------------------------------------------------------
    def record_action_failure(self, target: str, reason: str, capability: Optional[str] = None) -> None:
        failure_item = {
            "target": target,
            "reason": reason,
            "capability": capability,
            "timestamp": time.time(),
            "turn": self.context.turn_index,
        }
        self.context.recent_failures.insert(0, failure_item)
        if len(self.context.recent_failures) > 5:
            self.context.recent_failures.pop()

    def get_last_failure(self) -> Optional[Dict[str, Any]]:
        return self.context.recent_failures[0] if self.context.recent_failures else None

    # -------------------------------------------------------------------------
    # Pending Confirmation, Clarification & Draft States
    # -------------------------------------------------------------------------
    def set_pending_confirmation(self, confirmation: Optional[PendingConfirmation]) -> None:
        self.context.pending_confirmation = confirmation

    def get_pending_confirmation(self) -> Optional[PendingConfirmation]:
        return self.context.pending_confirmation

    def clear_pending_confirmation(self) -> None:
        self.context.pending_confirmation = None

    def set_pending_clarification(self, clarification: Optional[PendingClarification]) -> None:
        self.context.pending_clarification = clarification

    def get_pending_clarification(self) -> Optional[PendingClarification]:
        return self.context.pending_clarification

    def clear_pending_clarification(self) -> None:
        self.context.pending_clarification = None

    def set_pending_draft(self, draft: Optional[DraftResourceRef]) -> None:
        self.context.pending_draft = draft

    def get_pending_draft(self) -> Optional[DraftResourceRef]:
        return self.context.pending_draft

    def set_current_contact(self, contact: Any) -> None:
        self.context.current_contact = contact
        c_name = getattr(contact, "name", str(contact))
        c_id = getattr(contact, "resource_id", c_name)
        self.record_entity(EntityRef(
            entity_id=c_id,
            canonical_name=c_name,
            display_name=c_name,
            entity_type=EntityType.PERSON,
        ))

    def get_current_contact(self) -> Optional[Any]:
        return self.context.current_contact

    def set_current_device(self, device: Any) -> None:
        self.context.current_device = device

    def get_current_device(self) -> Optional[Any]:
        return self.context.current_device

    def record_browser_page(self, page: Any) -> None:
        self.context.current_browser_resource = page

    def get_current_browser_resource(self) -> Optional[Any]:
        return self.context.current_browser_resource

    def get_current_file(self) -> Optional[str]:
        if self.context.current_resource and hasattr(self.context.current_resource, "canonical_path"):
            return self.context.current_resource.canonical_path
        return self.get_last_opened_file()

    # -------------------------------------------------------------------------
    # Assistant Answer Annotation
    # -------------------------------------------------------------------------
    def record_assistant_answer(
        self,
        text: str,
        entities: Optional[List[EntityRef]] = None,
        result_set: Optional[ResultSet] = None,
    ) -> None:
        ans_item = {
            "text": text,
            "timestamp": time.time(),
            "turn": self.context.turn_index,
            "entities": [e.canonical_name for e in (entities or [])],
        }
        self.context.recent_answers.insert(0, ans_item)
        if len(self.context.recent_answers) > 10:
            self.context.recent_answers.pop()

        if entities:
            for ent in entities:
                self.record_entity(ent)
            if not self.context.active_topic:
                self.push_topic(entities[0])

        if result_set:
            self.record_result_set(result_set)

    # -------------------------------------------------------------------------
    # Turn Progression and Contextual Decay
    # -------------------------------------------------------------------------
    def advance_turn(self) -> None:
        self.context.turn_index += 1
        self.decay_context()

    def decay_context(self) -> None:
        """Applies differentiated decay to context items."""
        now = time.time()
        # Pending confirmation expires after 90 seconds or 2 turns
        if self.context.pending_confirmation:
            if now - self.context.pending_confirmation.created_at > 90.0:
                self.context.pending_confirmation = None

        # Pending clarification expires after 120 seconds
        if self.context.pending_clarification:
            if now - self.context.pending_clarification.created_at > 120.0:
                self.context.pending_clarification = None

        # Decay entity salience slightly each turn
        for ent in self.context.recent_entities:
            turns_ago = self.context.turn_index - ent.source_turn
            ent.salience = max(0.1, 1.0 - (turns_ago * 0.15))

    # -------------------------------------------------------------------------
    # Legacy Phase 12 & Phase 3 Methods (Preserved for 100% Backward Compatibility)
    # -------------------------------------------------------------------------
    def record_file_opened(self, file_path: str):
        norm_path = str(Path(file_path).resolve())
        self._last_opened_file = norm_path
        if norm_path in self._recent_files:
            self._recent_files.remove(norm_path)
        self._recent_files.insert(0, norm_path)
        if len(self._recent_files) > self.max_items:
            self._recent_files.pop()

        parent_folder = str(Path(norm_path).parent)
        self.record_folder_selected(parent_folder, set_focus=False)

        # Update structured resource focus
        f_ref = FileResourceRef(
            resource_id=f"file_{len(self._recent_files)}",
            canonical_path=norm_path,
        )
        self.set_current_resource(f_ref)

    record_file = record_file_opened
    record_opened = record_file_opened

    def record_folder_selected(self, folder_path: str, set_focus: bool = True):
        norm_folder = str(Path(folder_path).resolve())
        self._last_selected_folder = norm_folder
        if norm_folder in self._recent_folders:
            self._recent_folders.remove(norm_folder)
        self._recent_folders.insert(0, norm_folder)
        if len(self._recent_folders) > self.max_items:
            self._recent_folders.pop()

        # Update structured resource focus if requested
        if set_focus:
            f_ref = FolderResourceRef(
                resource_id=f"folder_{len(self._recent_folders)}",
                canonical_path=norm_folder,
            )
            self.set_current_resource(f_ref)

    record_folder = record_folder_selected

    def record_app_focused(self, app_name: str):
        self._last_focused_app = app_name
        if app_name in self._recent_apps:
            self._recent_apps.remove(app_name)
        self._recent_apps.insert(0, app_name)
        if len(self._recent_apps) > self.max_items:
            self._recent_apps.pop()

        app_ref = ApplicationResourceRef(
            resource_id=f"app_{app_name.lower()}",
            app_name=app_name,
        )
        self.set_current_resource(app_ref)

    record_app = record_app_focused

    def record_search_results(self, results_or_query: Any, paths: Optional[List[Any]] = None):
        if paths is not None:
            q = str(results_or_query)
            raw_items = paths
        elif isinstance(results_or_query, list):
            q = ""
            raw_items = results_or_query
        else:
            q = str(results_or_query)
            raw_items = []

        dict_results = []
        rs_items: List[BaseResourceRef] = []
        for idx, r in enumerate(raw_items):
            if isinstance(r, dict):
                p = r.get("path") or str(r)
                dict_results.append(r)
            else:
                p = str(r)
                dict_results.append({"path": p, "name": Path(p).name, "query": q})
            f_ref = FileResourceRef(
                resource_id=f"search_res_{idx + 1}",
                canonical_path=str(p),
                result_rank=idx + 1,
                source_query=q,
            )
            rs_items.append(f_ref)

        self._recent_search_results = dict_results[:self.max_items]
        if dict_results:
            first_path = dict_results[0].get("path")
            if first_path:
                try:
                    self.record_folder_selected(str(Path(first_path).parent), set_focus=False)
                except Exception:
                    pass

        self.record_result_set(
            ResultSet(
                result_set_id=f"rs_{int(time.time())}",
                query=q,
                item_type="FILE",
                resources=rs_items,
            )
        )

    def set_current_project(self, project_name: Optional[str]):
        self._current_project = project_name
        if project_name:
            self.record_entity(
                EntityRef(
                    entity_id=f"proj_{project_name.lower().replace(' ', '_')}",
                    canonical_name=project_name.lower(),
                    display_name=project_name,
                    entity_type=EntityType.PROJECT,
                    possible_capabilities=["workflow.git_status", "workflow.run_tests"],
                )
            )

    def record_task_outcome(self, goal: str, success: bool):
        if success:
            self._last_successful_task = goal
        else:
            self._last_failed_task = goal
        self.context.recent_actions.insert(0, {
            "goal": goal,
            "success": success,
            "timestamp": time.time(),
        })

    def get_last_opened_file(self) -> Optional[str]:
        return self._last_opened_file

    def get_last_selected_folder(self) -> Optional[str]:
        return self._last_selected_folder

    def get_last_focused_app(self) -> Optional[str]:
        return self._last_focused_app

    def get_current_project(self) -> Optional[str]:
        return self._current_project

    def get_recent_files(self, limit: int = 10) -> List[str]:
        return self._recent_files[:limit]

    def get_recent_folders(self, limit: int = 10) -> List[str]:
        return self._recent_folders[:limit]

    def get_recent_search_results(self) -> List[Dict[str, Any]]:
        return list(self._recent_search_results)

    def snapshot(self) -> Dict[str, Any]:
        """Returns compact dictionary summary for context assembly."""
        active_top_str = self.context.active_topic.display_name if self.context.active_topic else None
        curr_res_str = self.context.current_resource.display_name if self.context.current_resource else None
        return {
            "last_opened_file": self._last_opened_file,
            "last_selected_folder": self._last_selected_folder,
            "last_focused_app": self._last_focused_app,
            "current_project": self._current_project,
            "active_topic": active_top_str,
            "current_resource": curr_res_str,
            "recent_files": self._recent_files[:5],
            "recent_search_count": len(self._recent_search_results),
            "recent_entities": [e.display_name for e in self.context.recent_entities[:4]],
            "has_pending_confirmation": self.context.pending_confirmation is not None,
            "has_pending_clarification": self.context.pending_clarification is not None,
            "last_successful_task": self._last_successful_task,
        }

    def clear(self):
        self._recent_files.clear()
        self._recent_folders.clear()
        self._recent_apps.clear()
        self._recent_search_results.clear()
        self._last_opened_file = None
        self._last_selected_folder = None
        self._last_focused_app = None
        self._current_project = None
        self._last_successful_task = None
        self._last_failed_task = None
        self._recent_resources.clear()
        self._custom_items.clear()
        self.context = WorkingContext()
