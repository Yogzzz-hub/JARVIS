from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any
import yaml

@dataclass(frozen=True)
class IntentDefinition:
    name: str
    tool: str
    risk: str
    required_slots: tuple[str, ...]
    optional_slots: tuple[str, ...]
    compiled_patterns: tuple[re.Pattern, ...]
    keywords: tuple[str, ...]
    examples: tuple[str, ...]
    negative_examples: tuple[str, ...]
    aliases: dict[str, list[str]]
    fuzzy_allowed: bool
    fuzzy_threshold: float
    ambiguity_margin: float
    lane0_enabled: bool
    lane0_threshold: float
    lane1_threshold: float

class IntentCatalog:
    _instance: "IntentCatalog | None" = None

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path(__file__).resolve().parent / "intents.yaml"
        self.config_path = config_path
        self.intents: dict[str, IntentDefinition] = {}
        self.token_index: dict[str, list[str]] = {}
        self.all_intent_names: list[str] = []
        self._load()

    def _load(self):
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        for raw in data.get("intents", []):
            compiled = tuple(re.compile(p, re.IGNORECASE) for p in raw.get("patterns", []))
            defn = IntentDefinition(
                name=raw["name"],
                tool=raw["tool"],
                risk=raw.get("risk", "REVERSIBLE"),
                required_slots=tuple(raw.get("required_slots", [])),
                optional_slots=tuple(raw.get("optional_slots", [])),
                compiled_patterns=compiled,
                keywords=tuple(raw.get("keywords", [])),
                examples=tuple(raw.get("examples", [])),
                negative_examples=tuple(raw.get("negative_examples", [])),
                aliases=raw.get("aliases", {}),
                fuzzy_allowed=raw.get("fuzzy_allowed", True),
                fuzzy_threshold=float(raw.get("fuzzy_threshold", 80.0)),
                ambiguity_margin=float(raw.get("ambiguity_margin", 10.0)),
                lane0_enabled=raw.get("lane0_enabled", True),
                lane0_threshold=float(raw.get("lane0_threshold", 0.85)),
                lane1_threshold=float(raw.get("lane1_threshold", 0.70)),
            )
            self.intents[defn.name] = defn
            self.all_intent_names.append(defn.name)

            # Build token index from intent keywords and action words
            for kw in defn.keywords:
                for token in kw.split():
                    token_cf = token.casefold()
                    if token_cf not in self.token_index:
                        self.token_index[token_cf] = []
                    if defn.name not in self.token_index[token_cf]:
                        self.token_index[token_cf].append(defn.name)

    def retrieve_candidate_intents(self, tokens: list[str], max_candidates: int = 24) -> list[str]:
        """Retrieves candidate intent names from token index, prioritizing specific (rarer) tokens."""
        candidates: list[str] = []
        seen = set()

        # Sort tokens by rarity (fewer matching intents first) so specific words like "desktop" or "microphone" take precedence over generic words like "show"
        sorted_tokens = sorted(
            [t.casefold() for t in tokens if t.casefold() in self.token_index],
            key=lambda t: len(self.token_index[t]),
        )

        for cf in sorted_tokens:
            for intent_name in self.token_index[cf]:
                if intent_name not in seen:
                    seen.add(intent_name)
                    candidates.append(intent_name)
                    if len(candidates) >= max_candidates:
                        return candidates

        # If no candidates matched tokens, return standard common candidates
        if not candidates:
            return ["open_app", "get_time", "system_info", "volume_set", "take_screenshot"][:max_candidates]

        return candidates

    def is_known_app(self, name: str) -> bool:
        name_clean = name.strip().lower()
        if not name_clean or len(name_clean) > 40:
            return False
        action_prefixes = ("play ", "search ", "open ", "close ", "type ", "send ", "check ", "run ", "show ", "take ", "set ", "maximize", "minimize")
        if any(name_clean.startswith(prefix) for prefix in action_prefixes):
            return False
        open_defn = self.intents.get("open_app")
        if open_defn:
            if name_clean in open_defn.aliases:
                return True
            for k, vals in open_defn.aliases.items():
                if name_clean == k.lower() or name_clean in [v.lower() for v in vals]:
                    return True
            if name_clean in open_defn.keywords:
                return True
        if re.match(r"^[a-zA-Z0-9_\-\.\s]{2,30}$", name_clean):
            if name_clean not in {"and", "then", "please", "now", "it", "this", "app", "window"}:
                return True
        return False

    @classmethod
    def get_default(cls) -> "IntentCatalog":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

