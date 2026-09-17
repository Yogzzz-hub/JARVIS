"""Deterministic Decomposer for high-confidence common composition patterns (Phase 4).

Generates pre-validated, typed TaskGraphs for obvious two-step or three-step
workflows (e.g. find + open, find + copy, parallel dual-search, create + find + copy)
in < 2 ms without invoking an LLM.
"""

import os
import re
from typing import Optional
from jarvis.core.planner.schema import TaskGraph, TaskNode, ValueBinding


class DeterministicDecomposer:
    def __init__(self):
        # Compiled patterns
        self.p_find_open = re.compile(
            r"^(?:please\s+)?(?:find|search\s+for|locate)\s+(?:my\s+)?(.+?)\s+and\s+open\s+(?:it|that|the\s+file)$",
            re.IGNORECASE,
        )
        self.p_find_copy = re.compile(
            r"^(?:please\s+)?(?:find|search\s+for|locate)\s+(?:my\s+)?(.+?)\s+and\s+copy\s+(?:it|them)\s+(?:in|into|to)\s+(.+)$",
            re.IGNORECASE,
        )
        self.p_find_and_find = re.compile(
            r"^(?:please\s+)?(?:find|search\s+for|locate)\s+(?:my\s+)?(.+?)\s+and\s+(?:my\s+)?(.+?)$",
            re.IGNORECASE,
        )
        self.p_find_copy_open = re.compile(
            r"^(?:please\s+)?find\s+(?:my\s+)?(.+?),\s*(?:and\s+)?copy\s+(?:it|them)\s+(?:into|to)\s+(?:a\s+new\s+folder\s+called\s+)?(.+?)(?:\s+on\s+desktop)?\s+and\s+open\s+(?:both\s+)?(?:the\s+folder|it).*$",
            re.IGNORECASE,
        )
        self.p_create_find_copy = re.compile(
            r"^(?:please\s+)?create\s+(?:a\s+)?(?:new\s+)?folder\s+(?:called\s+)?(.+?)(?:\s+on\s+desktop)?\s+and\s+find\s+(?:my\s+)?(.+?),\s*then\s+copy\s+(?:it|the\s+file|the\s+pdf)\s+(?:into|to)\s+(?:the\s+folder|it)\s+and\s+open\s+(?:it|the\s+folder).*$",
            re.IGNORECASE,
        )

    def decompose(self, text: str) -> Optional[TaskGraph]:
        """Attempts deterministic decomposition into a typed TaskGraph."""
        clean = text.strip()

        # 1. Pattern: Find X, copy to new folder Y on Desktop, open folder
        m = self.p_find_copy_open.match(clean)
        if m:
            file_query = m.group(1).strip()
            folder_name = m.group(2).strip()
            return self._build_find_create_copy_open_graph(clean, file_query, folder_name)

        # 2. Pattern: Create folder Y, find X, copy and open
        m = self.p_create_find_copy.match(clean)
        if m:
            folder_name = m.group(1).strip()
            file_query = m.group(2).strip()
            return self._build_find_create_copy_open_graph(clean, file_query, folder_name)

        # 3. Pattern: Find X and open it
        m = self.p_find_open.match(clean)
        if m:
            query = m.group(1).strip()
            type_hint = self._extract_type_hint(query)
            clean_q = self._clean_query(query)
            return TaskGraph(
                goal=clean,
                goal_summary=f"Find and open {clean_q}",
                nodes=[
                    TaskNode(
                        id="n1",
                        tool="find_file",
                        args={"query": clean_q, "type_hint": type_hint} if type_hint else {"query": clean_q},
                        description=f"Search for {clean_q}",
                    ),
                    TaskNode(
                        id="n2",
                        tool="open_file",
                        depends_on=["n1"],
                        bindings={"path": ValueBinding(node_id="n1", output_path="results[0].path")},
                        description="Open the found file",
                    ),
                ],
            )

        # 4. Pattern: Find X and copy to Y
        m = self.p_find_copy.match(clean)
        if m:
            query = m.group(1).strip()
            destination = m.group(2).strip()
            type_hint = self._extract_type_hint(query)
            clean_q = self._clean_query(query)
            dest_path = self._resolve_dest(destination)
            return TaskGraph(
                goal=clean,
                goal_summary=f"Find {clean_q} and copy to {destination}",
                nodes=[
                    TaskNode(
                        id="n1",
                        tool="find_file",
                        args={"query": clean_q, "type_hint": type_hint} if type_hint else {"query": clean_q},
                        description=f"Search for {clean_q}",
                    ),
                    TaskNode(
                        id="n2",
                        tool="copy_file",
                        depends_on=["n1"],
                        args={"destination": dest_path},
                        bindings={"source": ValueBinding(node_id="n1", output_path="results[0].path")},
                        description=f"Copy file to {destination}",
                    ),
                ],
            )

        # 5. Pattern: Dual search ("Find my NLP notes and OS notes")
        m = self.p_find_and_find.match(clean)
        if m and "copy" not in clean.lower() and "open" not in clean.lower():
            q1 = m.group(1).strip()
            q2 = m.group(2).strip()
            # Verify both sound like search topics
            if len(q1) > 1 and len(q2) > 1:
                return TaskGraph(
                    goal=clean,
                    goal_summary=f"Concurrent search for {q1} and {q2}",
                    nodes=[
                        TaskNode(
                            id="n1",
                            tool="find_file",
                            args={"query": self._clean_query(q1), "type_hint": self._extract_type_hint(q1)},
                            description=f"Search for {q1}",
                        ),
                        TaskNode(
                            id="n2",
                            tool="find_file",
                            args={"query": self._clean_query(q2), "type_hint": self._extract_type_hint(q2)},
                            description=f"Search for {q2}",
                        ),
                    ],
                )

        return None

    def _build_find_create_copy_open_graph(self, goal: str, file_query: str, folder_name: str) -> TaskGraph:
        """Builds optimal 4-node parallel TaskGraph for Demonstration 1."""
        clean_q = self._clean_query(file_query)
        type_hint = self._extract_type_hint(file_query)
        folder_clean = folder_name.replace("called", "").replace("folder", "").strip()
        desktop_path = os.path.expanduser("~/Desktop")
        target_folder = os.path.join(desktop_path, folder_clean)

        find_args = {"query": clean_q}
        if type_hint:
            find_args["type_hint"] = type_hint

        return TaskGraph(
            goal=goal,
            goal_summary=f"Prepare {folder_clean} and copy {clean_q}",
            nodes=[
                # n1 and n2 run simultaneously (independent parallel roots)
                TaskNode(
                    id="n1",
                    tool="find_file",
                    args=find_args,
                    description=f"Find {clean_q}",
                ),
                TaskNode(
                    id="n2",
                    tool="create_folder",
                    args={"path": target_folder},
                    description=f"Create folder {folder_clean} on Desktop",
                ),
                # n3 depends on both n1 and n2
                TaskNode(
                    id="n3",
                    tool="copy_file",
                    depends_on=["n1", "n2"],
                    bindings={
                        "source": ValueBinding(node_id="n1", output_path="results[0].path"),
                        "destination": ValueBinding(node_id="n2", output_path="path"),
                    },
                    description=f"Copy found file into {folder_clean}",
                ),
                # n4 opens the folder (or file) after copy completes
                TaskNode(
                    id="n4",
                    tool="open_file",
                    depends_on=["n2", "n3"],
                    bindings={
                        "path": ValueBinding(node_id="n2", output_path="path"),
                    },
                    description=f"Open folder {folder_clean}",
                ),

            ],
        )

    def _clean_query(self, q: str) -> str:
        q = re.sub(r"\b(my|the|latest|recent|all)\b", "", q, flags=re.IGNORECASE)
        q = re.sub(r"\b(pdf|docx|doc|txt|notes|file|files)\b", "", q, flags=re.IGNORECASE)
        return " ".join(q.split()).strip()

    def _extract_type_hint(self, q: str) -> Optional[str]:
        ql = q.lower()
        if "pdf" in ql:
            return "pdf"
        if "docx" in ql or "doc" in ql:
            return "docx"
        if "txt" in ql:
            return "txt"
        return None

    def _resolve_dest(self, dest: str) -> str:
        dest_clean = dest.strip()
        if "desktop" in dest_clean.lower():
            return os.path.expanduser("~/Desktop")
        if "downloads" in dest_clean.lower():
            return os.path.expanduser("~/Downloads")
        if "documents" in dest_clean.lower():
            return os.path.expanduser("~/Documents")
        return dest_clean
