"""Route catalog auto-generated from the ToolRegistry + CapabilityRegistry (single source of truth).

Each capability's category/tool name maps to a JDE route family; family prototypes (descriptions,
examples, counterexamples) are assembled from the registries, so adding a tool automatically updates
JDE's semantic routes and capability shortlists. Families without tools (KNOWLEDGE, WEB, PLANNER,
CLARIFY, UNKNOWN) get fixed descriptions.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis.decision.schemas import ROUTE_FAMILIES

# tool-name rules first (more specific than categories)
_TOOL_RULES: list[tuple[str, str]] = [
    (r"^(?:android_pull_file|android_push_file|localsend_\w+)$", "TRANSFER"),
    (r"^android_|^android\.", "PHONE"),
    (r"whatsapp", "WHATSAPP"),
    (r"^(?:gmail|calendar|drive|google)_", "GOOGLE"),
    (r"^(?:install_software|uninstall_software|update_software|refresh_applications|check_app_installed|list_installed_applications|get_app_location)$", "PACKAGE"),
    (r"^(?:search_web|search_news|rss_latest)$", "WEB"),
    (r"^(?:web_task|browser_\w+|open_website|play_youtube)$", "BROWSER"),
    (r"^(?:media_control)$", "MEDIA"),
    (r"^(?:ollama_chat|agent_task)$", "KNOWLEDGE"),
    (r"^(?:knowledge_\w+|document_qa|search_notes|memos_recent)$", "RAG"),
    (r"^(?:set_reminder|list_reminders|capture_note|memos_create|quick_note|todo|stopwatch)$", "REMINDER"),
    (r"^(?:remember_fact|recall_facts|forget_fact)$", "RAG"),
    (r"^(?:quick_answer)$", "KNOWLEDGE"),
    (r"^(?:create_shortcut|list_shortcuts|delete_shortcut)$", "WORKFLOW"),
    (r"^(?:battery_status|network_info|command_history|generate_password|empty_recycle_bin)$", "SYSTEM"),
    (r"^(?:screen_click|computer_task|describe_screen|desktop_ui_\w+|dialog_interaction|keyboard_shortcut|dictate_text|"
     r"snap_window|arrange_windows|move_resize_window|switch_window|minimize_window|maximize_window|close_window|show_desktop)$", "DESKTOP"),
    (r"^(?:git_status|powershell_command|run_project_tests|diagnose_error|antigravity_ide_control)$", "DEVELOPMENT"),
    (r"^(?:morning_briefing|personal_briefing|launch_workspace|save_workspace|start_study_focus|wake_greeting)$", "WORKFLOW"),
    (r"^(?:open_app|close_app)$", "APP"),
    (r"^(?:find_file|open_file|copy_file|move_file|rename_file|delete_file|create_folder|list_directory|read_file_metadata|"
     r"find_duplicates|organize_downloads|batch_rename|open_known_folder|extract_audio|trim_media_clip)$", "FILE"),
]
_CATEGORY_FAMILY = {
    "SYSTEM": "SYSTEM", "HARDWARE": "SYSTEM", "APP": "APP", "WINDOWS": "DESKTOP", "BROWSER": "BROWSER", "FILE": "FILE",
    "RAG": "RAG", "PHONE": "PHONE", "WHATSAPP": "WHATSAPP", "GOOGLE": "GOOGLE", "WORKFLOW": "WORKFLOW",
    "TERMINAL": "DEVELOPMENT",
}

FIXED_FAMILIES: dict[str, dict[str, list[str]]] = {
    "KNOWLEDGE": {
        "description": ["Answer a general question, explain a concept, define a word, write or rewrite text, tell a joke, "
                        "have a conversation. No tool, no personal data, no fresh information."],
        "examples": ["what is machine learning", "explain how vaccines work", "write a poem about rain", "tell me a joke",
                     "how does WhatsApp encryption work", "what does delete mean", "who wrote Hamlet", "how are you"],
    },
    "WEB": {
        "description": ["Needs fresh or live information from the internet: news, weather, prices, scores, latest releases, "
                        "current events."],
        "examples": ["what's the weather in Chennai today", "latest TensorFlow release", "who won yesterday's match",
                     "bitcoin price right now", "today's headlines"],
    },
    "PLANNER": {
        "description": ["A goal needing several dependent steps across different kinds of tools: find something, use its result, "
                        "compare, then act."],
        "examples": ["find my latest invoice pdf and send it to my accountant on whatsapp",
                     "check my notes and compare them with the official docs then summarise what changed"],
    },
    "CLARIFY": {
        "description": ["The request refers to something that cannot be resolved (who is him, which file is it) or names an "
                        "ambiguous target; ask before acting."],
        "examples": ["send it to him", "open that", "delete them", "open studio"],
    },
    "UNKNOWN": {
        "description": ["Outside what JARVIS can do on this PC (physical world, other people's devices), nonsense, or empty."],
        "examples": ["make me a sandwich", "fly to mars", "asdkjh qwe", "hack my neighbour's wifi"],
    },
}


def family_for_tool(tool_name: str, category: str = "") -> str:
    for pattern, fam in _TOOL_RULES:
        if re.search(pattern, tool_name or ""):
            return fam
    if tool_name in ("volume_set", "volume_get", "brightness_set", "brightness_get", "get_time", "system_info",
                     "system_diagnostics", "take_screenshot", "system_power_control", "open_system_settings",
                     "top_memory_processes", "connected_devices", "microphone_status", "notification_send"):
        return "SYSTEM"
    return _CATEGORY_FAMILY.get((category or "").upper(), "SYSTEM")


@dataclass
class FamilyEntry:
    name: str
    descriptions: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    counterexamples: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    max_risk: str = "READ_ONLY"


_RISK_ORDER = ["READ_ONLY", "REVERSIBLE", "EXTERNAL_EFFECT", "DESTRUCTIVE", "PRIVILEGED"]


class RouteCatalog:
    def __init__(self, families: dict[str, FamilyEntry], tool_family: dict[str, str], tool_risk: dict[str, str]):
        self.families = families
        self.tool_family = tool_family
        self.tool_risk = tool_risk
        blob = "|".join(f"{k}:{','.join(sorted(v.tools))}:{len(v.examples)}" for k, v in sorted(families.items()))
        self.version = "cat-" + hashlib.sha1(blob.encode()).hexdigest()[:10]

    @classmethod
    def build(cls, capability_registry: Any = None, tool_registry: Any = None) -> "RouteCatalog":
        if capability_registry is None:
            from jarvis.core.capabilities.registry import get_default_capability_registry
            capability_registry = get_default_capability_registry()
        fams = {f: FamilyEntry(f) for f in ROUTE_FAMILIES}
        tool_family: dict[str, str] = {}
        tool_risk: dict[str, str] = {}
        for cap in capability_registry.list_all():
            category = getattr(cap.category, "value", str(cap.category))
            fam = family_for_tool(cap.target_tool, category)
            entry = fams[fam]
            entry.descriptions.append(cap.description)
            entry.examples.extend(cap.examples)
            entry.counterexamples.extend(cap.counterexamples)
            entry.capabilities.append(cap.id)
            if cap.target_tool and cap.target_tool not in entry.tools:
                entry.tools.append(cap.target_tool)
            risk = getattr(cap.risk_level, "name", str(cap.risk_level)).upper()
            tool_family[cap.target_tool] = fam
            tool_risk[cap.target_tool] = risk
            if risk in _RISK_ORDER and _RISK_ORDER.index(risk) > _RISK_ORDER.index(entry.max_risk):
                entry.max_risk = risk
        if tool_registry is not None:  # tools without a capability entry still belong to a family
            for tool in tool_registry.list():
                name = tool.definition.name
                if name not in tool_family:
                    fam = family_for_tool(name)
                    tool_family[name] = fam
                    fams[fam].tools.append(name)
                    fams[fam].descriptions.append(tool.definition.description)
                    tool_risk[name] = getattr(tool.definition.risk, "name", "READ_ONLY").upper()
        for name, spec in FIXED_FAMILIES.items():
            fams[name].descriptions.extend(spec["description"])
            fams[name].examples.extend(spec["examples"])
        return cls(fams, tool_family, tool_risk)

    def prototypes(self) -> dict[str, list[str]]:
        """Texts whose embeddings define each family in the semantic router."""
        return {f: (e.descriptions + e.examples) for f, e in self.families.items() if e.descriptions or e.examples}

    def risk_of(self, family: str) -> str:
        entry = self.families.get(family)
        return entry.max_risk if entry else "READ_ONLY"

    def tools_for(self, families: list[str]) -> list[str]:
        out: list[str] = []
        for f in families:
            for t in self.families.get(f, FamilyEntry(f)).tools:
                if t not in out:
                    out.append(t)
        return out


_default: Optional[RouteCatalog] = None


def default_catalog() -> RouteCatalog:
    global _default
    if _default is None:
        _default = RouteCatalog.build()
    return _default
