"""Tool retrieval and prompt rendering shared by every model-driven lane.

The router classifier, the DAG planner and the agent loop all need the same
thing: "given this request, which of the ~100 registered tools are relevant,
and how do I describe them to a small local model?". Retrieval is RAG over the
tool registry (lexical tool retriever + semantic capability retriever), and the
descriptions are generated from each tool's real pydantic input model, so the
model is only ever told about tools that exist, with the argument names the
validator will accept.
"""
from __future__ import annotations

import logging
import types
import weakref
from typing import Any, Iterable, Optional, Union, get_args, get_origin

from pydantic import BaseModel

from jarvis.tools.base import RiskLevel, Tool

logger = logging.getLogger("jarvis.llm.tools")

# Tools that an AI-originated call (agent / planner) may only run after the
# user confirms, even when the static policy would allow a direct command.
AI_CONFIRM_TOOLS = frozenset({
    "powershell_command",
    "install_software",
    "delete_file",
    "move_file",
    "rename_file",
    "batch_rename",
    "organize_downloads",
    "system_power_control",
    "run_project_tests",
    "close_app",
    "send_whatsapp_message",
    "localsend_file",
    "localsend_text",
    "notification_send",
    "android_dial",
})

# Tools never offered to the agent: they are UI plumbing or would recurse.
AGENT_EXCLUDED_TOOLS = frozenset({
    "ollama_chat",
    "agent_task",
    "show_dashboard",
    "wake_greeting",
    "set_voice",
    "dictation_mode_control",
    "voice_edit",
    "whatsapp_action",
    "reply_whatsapp_message",
})

_retrievers: "weakref.WeakKeyDictionary[Any, Any]" = weakref.WeakKeyDictionary()

# Slot names produced by the router / capability registry that differ from a tool's argument names.
SLOT_ALIASES: dict[str, dict[str, str]] = {
    "document_qa": {"path": "document_path", "file_path": "document_path", "file": "document_path", "query": "question"},
    "knowledge_search": {"query": "question"},
    "knowledge_ingest": {"folder": "path", "file_path": "path"},
    "send_whatsapp_message": {"to": "recipient", "contact": "recipient", "name": "recipient", "text": "message", "body": "message"},
    "reply_whatsapp_message": {"to": "recipient", "contact": "recipient", "name": "recipient"},
    "android_open_app": {"app": "app_name", "name": "app_name"},
    "search_web": {"q": "query", "question": "query"},
    "ollama_chat": {"question": "query", "text": "query"},
    "web_task": {"task": "goal", "query": "goal"},
    "agent_task": {"task": "goal", "query": "goal"},
}


def normalize_slots(tool_name: str, slots: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Rename known slot aliases to the tool's real argument names (never overwrites a real value)."""
    slots = dict(slots or {})
    for alias, target in SLOT_ALIASES.get(tool_name, {}).items():
        if alias in slots and target not in slots:
            slots[target] = slots.pop(alias)
    return slots


def _type_name(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation)).replace("NoneType", "null")
    args = [a for a in get_args(annotation) if a is not type(None)]
    if origin in (list, tuple, set):
        return f"list[{_type_name(args[0]) if args else 'any'}]"
    if origin is dict:
        return "object"
    if len(args) == 1:
        return f"{_type_name(args[0])}?"
    return "|".join(_type_name(a) for a in args)


def argument_spec(model: type[BaseModel]) -> tuple[dict[str, str], list[str]]:
    """Return ``({field: "type - description"}, required_fields)`` for a tool input model."""
    fields: dict[str, str] = {}
    required: list[str] = []
    for name, info in model.model_fields.items():
        if name in ("confirmation_ticket",):
            continue
        desc = (info.description or "").strip()
        type_str = _type_name(info.annotation)
        fields[name] = f"{type_str} - {desc}" if desc else type_str
        if info.is_required():
            required.append(name)
    return fields, required


def describe_tool(tool: Tool, max_desc: int = 180) -> str:
    defn = tool.definition
    fields, required = argument_spec(defn.input_model)
    desc = defn.description.strip().split("\n")[0]
    if len(desc) > max_desc:
        desc = desc[: max_desc - 3] + "..."
    args = []
    for name, spec in fields.items():
        marker = "*" if name in required else ""
        args.append(f"{name}{marker}: {spec}")
    arg_str = "; ".join(args) if args else "no arguments"
    risk = defn.risk.value if hasattr(defn.risk, "value") else str(defn.risk)
    return f"- {defn.name} [{risk}] {desc} Args: {arg_str}"


def render_tools(tools: Iterable[Tool]) -> str:
    return "\n".join(describe_tool(t) for t in tools)


def _tool_retriever(registry: Any):
    try:
        cached = _retrievers.get(registry)
    except TypeError:
        cached = None
    if cached is None:
        from jarvis.core.planner.tool_retriever import ToolRetriever
        cached = ToolRetriever(registry)
        try:
            _retrievers[registry] = cached
        except TypeError:
            pass
    return cached


def select_tools(
    query: str,
    registry: Any,
    top_k: int = 10,
    capability_retriever: Any = None,
    include: Iterable[str] = (),
    exclude: Iterable[str] = AGENT_EXCLUDED_TOOLS,
) -> list[Tool]:
    """Retrieve the tools most relevant to ``query`` (RAG over the tool registry)."""
    if registry is None:
        return []
    excluded = set(exclude)
    ordered: list[str] = []

    def add(name: str) -> None:
        if name and name not in excluded and name not in ordered and registry.contains(name):
            ordered.append(name)

    for name in include:
        add(name)

    if capability_retriever is not None:
        try:
            for cap, _score in capability_retriever.retrieve(query, top_k=top_k, min_score=2.0):
                add(cap.target_tool)
        except Exception as exc:
            logger.debug("Capability retrieval failed: %s", exc)

    try:
        for schema in _tool_retriever(registry).retrieve(query, top_k=top_k):
            add(schema.name)
    except Exception as exc:
        logger.debug("Tool retrieval failed: %s", exc)

    tools = []
    for name in ordered[: max(top_k, len(tuple(include)))]:
        try:
            tools.append(registry.get(name))
        except KeyError:
            continue
    return tools


def _unwrap_optional(annotation: Any) -> Any:
    """``Optional[X]`` -> ``X``; other unions -> None (left untouched); plain types unchanged."""
    if get_origin(annotation) in (Union, types.UnionType):
        members = [a for a in get_args(annotation) if a is not type(None)]
        return members[0] if len(members) == 1 else None
    return annotation


def filter_arguments(tool: Tool, raw: Optional[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Keep only arguments the tool accepts and coerce simple types; report missing required ones."""
    model = tool.definition.input_model
    raw = normalize_slots(tool.definition.name, raw)
    clean: dict[str, Any] = {}
    for name, info in model.model_fields.items():
        if name not in raw or raw[name] is None or raw[name] == "":
            continue
        value = raw[name]
        kind = _unwrap_optional(info.annotation)
        try:
            if kind is int and not isinstance(value, bool):
                value = int(float(value))
            elif kind is float:
                value = float(value)
            elif kind is bool and isinstance(value, str):
                value = value.strip().lower() in ("true", "yes", "1", "on")
            elif kind is str and not isinstance(value, str):
                value = str(value)
            elif get_origin(kind) in (list, tuple) and isinstance(value, str):
                value = [value]
        except (TypeError, ValueError):
            continue
        clean[name] = value
    missing = [n for n, info in model.model_fields.items() if info.is_required() and n not in clean]
    return clean, missing


def needs_ai_confirmation(tool: Tool) -> bool:
    """AI-originated calls to risky tools always go back to the user first."""
    defn = tool.definition
    if defn.name in AI_CONFIRM_TOOLS:
        return True
    return defn.risk in (RiskLevel.EXTERNAL_EFFECT, RiskLevel.DESTRUCTIVE, RiskLevel.PRIVILEGED)


def available_capabilities_summary(registry: Any, max_tools: int = 60) -> str:
    """Short, truthful list of what this deployment can do (from the live registry)."""
    if registry is None:
        return ""
    groups: dict[str, list[str]] = {}
    for tool in registry.list():
        name = tool.definition.name
        if name in AGENT_EXCLUDED_TOOLS:
            continue
        if name.startswith(("android_", "localsend_")):
            key = "Phone"
        elif "whatsapp" in name:
            key = "WhatsApp"
        elif name.startswith("browser_") or name in ("search_web", "play_youtube", "search_news", "web_task"):
            key = "Web & browser"
        elif name.startswith(("gmail_", "calendar_", "drive_")):
            key = "Google"
        elif name in ("find_file", "open_file", "copy_file", "move_file", "rename_file", "delete_file", "create_folder",
                      "list_directory", "read_file_metadata", "find_duplicates", "organize_downloads", "batch_rename"):
            key = "Files"
        elif name in ("document_qa", "knowledge_ingest", "knowledge_search", "capture_note", "search_notes", "memos_create", "memos_recent"):
            key = "Knowledge & notes"
        else:
            key = "PC control"
        groups.setdefault(key, []).append(name)
    lines = []
    count = 0
    for key in sorted(groups):
        names = groups[key]
        remaining = max_tools - count
        if remaining <= 0:
            break
        lines.append(f"- {key}: {', '.join(names[:remaining])}")
        count += len(names[:remaining])
    return "\n".join(lines)
