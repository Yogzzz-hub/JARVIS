"""Window Discovery and Deterministic Targeting."""
from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional
from jarvis.core.computer.windows.backend import WindowsUIABackend


class WindowManager:
    """Manages window discovery, title matching, and deterministic target resolution."""

    def __init__(self, backend: Optional[WindowsUIABackend] = None) -> None:
        self.backend = backend or WindowsUIABackend()

    def list_windows(
        self,
        process_name: Optional[str] = None,
        title_query: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List active desktop windows filtered by optional criteria."""
        all_windows = self.backend.list_windows()
        filtered = []

        for w in all_windows:
            if title_query and title_query.lower() not in w["window_title"].lower():
                continue
            if process_name and process_name.lower() not in w.get("class_name", "").lower():
                continue
            filtered.append(w)
            if len(filtered) >= limit:
                break

        return filtered

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get the current foreground / active window."""
        windows = self.backend.list_windows()
        for w in windows:
            if w.get("foreground"):
                return w
        return windows[0] if windows else None

    def resolve_target_window(
        self,
        query: str,
        active_hint: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, Any]], str]:
        """Resolve a target window deterministically with ambiguity detection.
        
        Returns: (window_info, status) where status is 'FOUND', 'AMBIGUOUS', or 'NOT_FOUND'.
        """
        all_windows = self.backend.list_windows()
        if not all_windows:
            return None, "NOT_FOUND"

        query_clean = query.strip().lower()

        # 1. Exact match on title
        exact_matches = [w for w in all_windows if w["window_title"].strip().lower() == query_clean]
        if len(exact_matches) == 1:
            return exact_matches[0], "FOUND"
        elif len(exact_matches) > 1:
            return None, "AMBIGUOUS"

        # 2. Substring match on title
        sub_matches = [w for w in all_windows if query_clean in w["window_title"].lower()]
        if len(sub_matches) == 1:
            return sub_matches[0], "FOUND"
        elif len(sub_matches) > 1:
            # Check if one is currently in foreground
            fg_matches = [w for w in sub_matches if w.get("foreground")]
            if len(fg_matches) == 1:
                return fg_matches[0], "FOUND"
            return None, "AMBIGUOUS"

        # 3. Fuzzy match
        titles = [w["window_title"] for w in all_windows]
        matches = difflib.get_close_matches(query, titles, n=3, cutoff=0.6)
        if len(matches) == 1:
            for w in all_windows:
                if w["window_title"] == matches[0]:
                    return w, "FOUND"
        elif len(matches) > 1:
            return None, "AMBIGUOUS"

        return None, "NOT_FOUND"
