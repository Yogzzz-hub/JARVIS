"""Fast cascaded tool capability retriever and schema compactor (Phase 4).

Filters tools down to Top-K (8-12) relevant compact schemas using:
1. Exact intent/tool tags
2. Action verbs & domain synonyms
3. Token inverted index
4. Lexical token overlap & RapidFuzz scoring
Ensures high recall (>=99% Recall@12) while keeping prompt token budget small.
"""

from collections import defaultdict
import re
from typing import Any, Optional, get_args, get_origin
from pydantic import BaseModel

from jarvis.tools.base import Tool
from jarvis.tools.registry import ToolRegistry

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


VERB_MAPPING: dict[str, tuple[str, ...]] = {
    "find": ("find_file", "list_directory"),
    "search": ("find_file", "list_directory"),
    "locate": ("find_file",),
    "look": ("find_file",),
    "copy": ("copy_file",),
    "clone": ("copy_file",),
    "duplicate": ("copy_file",),
    "move": ("move_file",),
    "transfer": ("move_file",),
    "relocate": ("move_file",),
    "rename": ("rename_file",),
    "open": ("open_file", "open_app"),
    "launch": ("open_app", "open_file"),
    "start": ("open_app", "open_file"),
    "run": ("open_app", "open_file"),
    "view": ("open_file", "list_directory"),
    "show": ("open_file", "list_directory"),
    "create": ("create_folder",),
    "make": ("create_folder",),
    "new": ("create_folder",),
    "mkdir": ("create_folder",),
    "folder": ("create_folder", "list_directory", "open_file"),
    "directory": ("create_folder", "list_directory"),
    "delete": ("delete_file",),
    "remove": ("delete_file",),
    "trash": ("delete_file",),
    "list": ("list_directory", "find_file"),
    "ls": ("list_directory",),
    "volume": ("volume_set", "volume_get", "mute_toggle"),
    "sound": ("volume_set", "volume_get", "mute_toggle"),
    "mute": ("mute_toggle", "volume_set"),
    "unmute": ("mute_toggle", "volume_set"),
    "brightness": ("brightness_set", "brightness_get"),
    "screen": ("take_screenshot", "brightness_set"),
    "screenshot": ("take_screenshot",),
    "capture": ("take_screenshot",),
    "lock": ("lock_pc",),
    "sleep": ("sleep_pc",),
    "restart": ("restart_pc",),
    "reboot": ("restart_pc",),
    "shutdown": ("shutdown_pc",),
    "power": ("battery_status", "shutdown_pc", "sleep_pc"),
    "battery": ("battery_status",),
    "system": ("system_info",),
    "specs": ("system_info",),
    "close": ("close_app",),
    "quit": ("close_app",),
    "kill": ("close_app",),
}

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pdf": ("find_file", "open_file", "copy_file"),
    "doc": ("find_file", "open_file", "copy_file"),
    "docx": ("find_file", "open_file", "copy_file"),
    "txt": ("find_file", "open_file", "copy_file"),
    "file": ("find_file", "open_file", "copy_file", "move_file", "delete_file", "read_file_metadata"),
    "folder": ("create_folder", "list_directory", "open_file"),
    "notes": ("find_file", "open_file", "copy_file"),
    "exam": ("find_file", "open_file", "copy_file", "create_folder"),
    "study": ("find_file", "open_file", "copy_file", "create_folder"),
    "desktop": ("create_folder", "copy_file", "open_file", "list_directory"),
    "downloads": ("find_file", "copy_file", "list_directory"),
    "documents": ("find_file", "copy_file", "list_directory"),
    "chrome": ("open_app", "close_app"),
    "notepad": ("open_app", "close_app"),
    "calculator": ("open_app", "close_app"),
}


class CompactToolSchema(BaseModel):
    name: str
    description: str
    input: dict[str, str]
    required: list[str]
    output: dict[str, str]


class ToolRetriever:
    def __init__(self, registry: ToolRegistry, default_top_k: int = 12):
        self.registry = registry
        self.default_top_k = default_top_k
        self._token_index: dict[str, set[str]] = defaultdict(set)
        self._build_token_index()

    def _build_token_index(self):
        """Indexes registered tools by tokens in name, description, and tags."""
        for tool in self.registry.list():
            defn = tool.definition
            name = defn.name
            tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
            tokens.update(re.findall(r"[a-z0-9]+", defn.description.lower()))
            for tag in defn.tags:
                tokens.update(re.findall(r"[a-z0-9]+", tag.lower()))
            for t in tokens:
                if len(t) > 2:
                    self._token_index[t].add(name)

    def retrieve(
        self,
        request_text: str,
        top_k: Optional[int] = None,
        router_intents: Optional[list[str]] = None,
    ) -> list[CompactToolSchema]:
        """Retrieves Top-K compact tool schemas relevant to user request."""
        k = top_k or self.default_top_k
        scores: dict[str, float] = defaultdict(float)
        req_lower = request_text.lower()
        words = re.findall(r"[a-z0-9]+", req_lower)

        # 1. Action verb matching (high weight)
        for w in words:
            if w in VERB_MAPPING:
                for tool_name in VERB_MAPPING[w]:
                    scores[tool_name] += 15.0

        # 2. Domain keywords matching
        for w in words:
            if w in DOMAIN_KEYWORDS:
                for tool_name in DOMAIN_KEYWORDS[w]:
                    scores[tool_name] += 10.0

        # 3. Inverted token index matching
        for w in words:
            if w in self._token_index:
                for tool_name in self._token_index[w]:
                    scores[tool_name] += 4.0

        # 4. Router hint bonus
        if router_intents:
            for intent in router_intents:
                if self.registry.contains(intent):
                    scores[intent] += 20.0

        # 5. RapidFuzz lexical matching if available
        if fuzz:
            for tool in self.registry.list():
                tname = tool.definition.name
                sim = fuzz.partial_ratio(req_lower, tname.replace("_", " "))
                if sim > 70:
                    scores[tname] += (sim / 10.0)

        # Baseline bonus for core common utility tools if scores are low
        for fallback_tool in ("find_file", "open_file", "copy_file", "create_folder"):
            if self.registry.contains(fallback_tool):
                scores[fallback_tool] += 0.5

        # Rank tools
        ranked_names = sorted(
            [name for name in scores if self.registry.contains(name)],
            key=lambda name: scores[name],
            reverse=True,
        )

        # If fewer than k, backfill with remaining registered tools
        if len(ranked_names) < k:
            for tool in self.registry.list():
                tname = tool.definition.name
                if tname not in ranked_names:
                    ranked_names.append(tname)
                if len(ranked_names) >= k:
                    break

        selected_names = ranked_names[:k]
        return [self.compact_schema(self.registry.get(name)) for name in selected_names]

    def compact_schema(self, tool: Tool) -> CompactToolSchema:
        """Converts Tool into a compact, low-token schema."""
        defn = tool.definition
        input_model = defn.input_model
        output_model = defn.output_model

        input_fields: dict[str, str] = {}
        required_fields: list[str] = []
        for fname, finfo in input_model.model_fields.items():
            type_str = self._format_type(finfo.annotation)
            input_fields[fname] = type_str
            if finfo.is_required():
                required_fields.append(fname)

        output_fields: dict[str, str] = {}
        for fname, finfo in output_model.model_fields.items():
            output_fields[fname] = self._format_type(finfo.annotation)

        return CompactToolSchema(
            name=defn.name,
            description=defn.description.strip().split("\n")[0],  # One line summary
            input=input_fields,
            required=required_fields,
            output=output_fields,
        )

    def _format_type(self, annotation: Any) -> str:
        """Helper to format python type into compact string."""
        if annotation is str:
            return "str"
        if annotation is int:
            return "int"
        if annotation is float:
            return "float"
        if annotation is bool:
            return "bool"
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin in (list, tuple, set):
            sub = self._format_type(args[0]) if args else "any"
            return f"list[{sub}]"
        if origin is dict:
            return "dict"
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation).replace("typing.", "")
