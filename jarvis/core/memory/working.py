"""Ultra-fast bounded working memory for active interaction context (Phase 12)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.core.memory.models import MemoryItem, MemoryLayer, MemoryProvenance, MemorySourceType, MemoryConfidence


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
        self._recent_resources: List[Dict[str, Any]] = []
        self._custom_items: Dict[str, MemoryItem] = {}

    def record_file_opened(self, file_path: str):
        norm_path = str(Path(file_path).resolve())
        self._last_opened_file = norm_path
        if norm_path in self._recent_files:
            self._recent_files.remove(norm_path)
        self._recent_files.insert(0, norm_path)
        if len(self._recent_files) > self.max_items:
            self._recent_files.pop()

        parent_folder = str(Path(norm_path).parent)
        self.record_folder_selected(parent_folder)

    def record_folder_selected(self, folder_path: str):
        norm_folder = str(Path(folder_path).resolve())
        self._last_selected_folder = norm_folder
        if norm_folder in self._recent_folders:
            self._recent_folders.remove(norm_folder)
        self._recent_folders.insert(0, norm_folder)
        if len(self._recent_folders) > self.max_items:
            self._recent_folders.pop()

    def record_app_focused(self, app_name: str):
        self._last_focused_app = app_name
        if app_name in self._recent_apps:
            self._recent_apps.remove(app_name)
        self._recent_apps.insert(0, app_name)
        if len(self._recent_apps) > self.max_items:
            self._recent_apps.pop()

    def record_search_results(self, results: List[Dict[str, Any]]):
        self._recent_search_results = results[:self.max_items]
        if results:
            first_path = results[0].get("path")
            if first_path:
                self.record_folder_selected(str(Path(first_path).parent))

    def set_current_project(self, project_name: Optional[str]):
        self._current_project = project_name

    def record_task_outcome(self, goal: str, success: bool):
        if success:
            self._last_successful_task = goal
        else:
            self._last_failed_task = goal

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
        return {
            "last_opened_file": self._last_opened_file,
            "last_selected_folder": self._last_selected_folder,
            "last_focused_app": self._last_focused_app,
            "current_project": self._current_project,
            "recent_files": self._recent_files[:5],
            "recent_search_count": len(self._recent_search_results),
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
