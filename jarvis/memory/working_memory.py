from pathlib import Path
import re
from jarvis.memory.search.models import SearchQuery, SearchResult

class WorkingMemory:
    """Maintains active working session context for resolving conversational pronouns."""
    def __init__(self, max_recent_results: int = 20):
        self.max_recent = max_recent_results
        self.last_query: SearchQuery | None = None
        self.last_results: list[SearchResult] = []
        self.last_opened_file: str | None = None
        self.last_folder: str | None = None
        self.last_type: str | None = None

    def record_search(self, query: SearchQuery, results: list[SearchResult]):
        self.last_query = query
        self.last_results = results[:self.max_recent]
        if results:
            self.last_folder = str(Path(results[0].path).parent)
            self.last_type = results[0].extension

    def record_opened(self, file_path: str):
        self.last_opened_file = file_path
        self.last_folder = str(Path(file_path).parent)
        self.last_type = Path(file_path).suffix.casefold()

    def set_last_folder(self, folder: str):
        self.last_folder = folder

    def get_context_file_ids(self) -> set[int]:
        return {r.file_id for r in self.last_results}

    def resolve_reference(self, utterance: str) -> SearchResult | str | None:
        """Resolves conversational references like 'open that file', 'the second one', 'that folder'."""
        text = utterance.strip().casefold()

        # 1. Folder reference ("open that folder", "same folder")
        if any(p in text for p in ("that folder", "same folder", "that directory", "the folder")):
            if self.last_folder:
                return self.last_folder
            if self.last_opened_file:
                return str(Path(self.last_opened_file).parent)
            if self.last_results:
                return str(Path(self.last_results[0].path).parent)
            return None

        # 2. Positional ordinal reference ("the first one", "the second one", etc.)
        ordinal_map = {
            "first": 0, "1st": 0,
            "second": 1, "2nd": 1,
            "third": 2, "3rd": 2,
            "fourth": 3, "4th": 3,
            "fifth": 4, "5th": 4,
            "last": -1,
        }
        for ord_word, idx in ordinal_map.items():
            if f"the {ord_word}" in text or f"{ord_word} one" in text:
                if self.last_results:
                    if idx == -1:
                        return self.last_results[-1]
                    if 0 <= idx < len(self.last_results):
                        return self.last_results[idx]
                return None

        # 3. Type-filtered reference ("the pdf", "that pdf", "open the document")
        if "pdf" in text and self.last_results:
            for r in self.last_results:
                if r.extension == ".pdf":
                    return r

        # 4. Direct pronoun ("open that file", "that document", "open that", "that one")
        if any(p in text for p in ("that file", "that document", "that one", "open that")):
            if self.last_opened_file:
                return self.last_opened_file
            if self.last_results:
                return self.last_results[0]

        return None
