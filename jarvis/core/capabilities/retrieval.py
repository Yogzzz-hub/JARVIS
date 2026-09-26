"""Fast BM25 & Semantic Hybrid Capability Retriever with Family & Resource Typing.

Combines:
- BM25 lexical term weighting
- Morphological stemming & conceptual synonym normalization
- Capability family routing (FILE, APP, BROWSER, PHONE, WHATSAPP, SYSTEM, RAG, WORKFLOW)
- Resource-type compatibility boosts & domain mismatch penalties
- Working memory context awareness (anaphoric referents, recent search results)
- Multi-clause conjunction splitting for compound/workflow retrieval
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from jarvis.core.capabilities.models import CapabilityCategory, CapabilityDefinition
from jarvis.core.capabilities.registry import CapabilityRegistry, get_default_capability_registry


# Common English suffix patterns for rule-based stemming
STEM_SUFFIXES = (
    ("sses", "ss"), ("ies", "i"), ("ss", "ss"), ("s", ""),
    ("eed", "ee"), ("ed", ""), ("ing", ""), ("ly", ""),
    ("ment", ""), ("tion", ""), ("ness", ""), ("able", ""),
)

STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "from", "of", "with", "by",
    "as", "is", "it", "its", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "this", "that", "these", "those",
    "my", "your", "his", "her", "their", "our", "me", "him", "them", "us",
    "i", "you", "he", "she", "we", "they", "what", "which", "who", "whom",
    "where", "when", "why", "how", "all", "any", "both", "each", "few",
    "more", "most", "some", "such", "no", "nor", "too", "very", "can", "will",
    "just", "should", "would", "now", "here", "there", "up", "down", "out",
    "about", "into", "over", "after", "then", "also", "please", "could", "kindly",
    "sir", "jarvis", "want", "need", "like", "get", "make", "put", "let"
}

SYNONYM_MAP = {
    # App lifecycle
    "launch": "open", "fire": "open", "spawn": "open", "start": "open",
    "bring": "open", "display": "open", "run": "open", "pop": "open",
    "shut": "close", "kill": "close", "terminate": "close", "dismiss": "close", "exit": "close",
    # Search / Files
    "find": "search", "locate": "search", "seek": "search", "scan": "search",
    "tidy": "organize", "sort": "organize", "clean": "organize",
    "cloned": "duplicate", "repeated": "duplicate", "redundant": "duplicate",
    # Volume / Audio
    "sound": "volume", "loudness": "volume", "audio": "volume", "speaker": "volume",
    "silence": "mute", "quiet": "mute", "valume": "volume", "volum": "volume",
    "louder": "volume", "softer": "volume",
    # Screen / Hardware
    "snapshot": "screenshot", "grab": "screenshot", "snip": "screenshot", "capture": "screenshot",
    "specs": "info", "specifications": "info", "ram": "memory", "hardware": "info",
    "health": "diagnostics", "audit": "diagnostics", "checkup": "diagnostics",
    "clock": "time", "hour": "time", "date": "time", "timestamp": "time",
    "juice": "battery", "charge": "battery", "power": "battery",
    # Brightness / Light
    "dim": "brightness", "brighten": "brightness", "lights": "brightness", "backlight": "brightness",
    # Device / external
    "android": "phone", "mobile": "phone", "handset": "phone", "cell": "phone",
    "memo": "note", "jot": "note", "bullet": "summarize", "takeaways": "summarize",
    "headlines": "news", "rss": "news", "feed": "news",
    # Transfer / Send
    "transfer": "send", "push": "send", "beam": "send", "transmit": "send", "dispatch": "send",
    # Window
    "expand": "maximize", "enlarge": "maximize",
    "drop": "minimize", "hide": "minimize",
}


def _stem_and_normalize(word: str) -> str:
    w = word.lower().strip()
    if w in SYNONYM_MAP:
        w = SYNONYM_MAP[w]
    for suf, rep in STEM_SUFFIXES:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            w = w[:-len(suf)] + rep
            break
    if w in SYNONYM_MAP:
        w = SYNONYM_MAP[w]
    return w



_PHONE_MENTION = re.compile(r"\b(?:phone|mobile|android|smartphone|cell ?phone|handset)\b")

_NUMBER_WORDS = re.compile(r"\b(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|percent|%)\b")


class CapabilityRetriever:
    """
    Sub-millisecond BM25 and semantic hybrid capability retriever with
    family routing, resource-type compatibility, and contextual state inference.
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry or get_default_capability_registry()
        self._build_index()

    def _keyword_patterns(self, cap: CapabilityDefinition) -> List[Tuple[str, "re.Pattern[str]"]]:
        cached = self._kw_cache.get(cap.id)
        if cached is None:
            cached = []
            for kw in cap.keywords:
                kw_clean = kw.lower().strip()
                if kw_clean:
                    cached.append((kw_clean, re.compile(r"\b" + re.escape(kw_clean) + r"\b")))
            self._kw_cache[cap.id] = cached
        return cached

    def _build_index(self) -> None:
        self._kw_cache: Dict[str, List[Tuple[str, "re.Pattern[str]"]]] = {}
        self.capabilities = self.registry.list_all()
        self.doc_count = len(self.capabilities)
        self.doc_tokens: Dict[str, Counter] = {}
        self.doc_norm_tokens: Dict[str, Set[str]] = {}
        self.df: Dict[str, int] = defaultdict(int)
        self.family_map: Dict[str, List[CapabilityDefinition]] = defaultdict(list)

        for cap in self.capabilities:
            fam = self._get_cap_family(cap)
            self.family_map[fam].append(cap)

            terms: List[str] = []
            norm_set: Set[str] = set()
            for ex in cap.examples:
                ex_words = [w for w in re.findall(r"\w+", ex.lower()) if w not in STOPWORDS]
                terms.extend(ex_words * 3)
                norm_set.update(_stem_and_normalize(w) for w in ex_words if _stem_and_normalize(w) not in STOPWORDS)
            for kw in cap.keywords:
                kw_words = [w for w in re.findall(r"\w+", kw.lower()) if w not in STOPWORDS]
                terms.extend(kw_words * 2)
                norm_set.update(_stem_and_normalize(w) for w in kw_words if _stem_and_normalize(w) not in STOPWORDS)
            desc_words = [w for w in re.findall(r"\w+", cap.description.lower()) if w not in STOPWORDS]
            terms.extend(desc_words)
            norm_set.update(_stem_and_normalize(w) for w in desc_words if _stem_and_normalize(w) not in STOPWORDS)

            # Add capability id tokens (e.g. file, find)
            id_parts = cap.id.replace("_", " ").replace(".", " ").split()
            terms.extend(id_parts * 2)
            norm_set.update(_stem_and_normalize(p) for p in id_parts if p not in STOPWORDS)

            tokens = Counter(terms)
            self.doc_tokens[cap.id] = tokens
            self.doc_norm_tokens[cap.id] = norm_set
            for tok in tokens:
                self.df[tok] += 1

    def _get_cap_family(self, cap: CapabilityDefinition) -> str:
        if hasattr(cap, "get_family"):
            return cap.get_family()
        parts = cap.id.split(".")
        if len(parts) >= 2:
            p = parts[0].upper()
            if p == "WINDOWS":
                return "SYSTEM"
            return p
        return cap.category.value

    def _infer_families_and_resources(self, text: str) -> Tuple[Set[str], Set[str]]:
        ql = text.lower()
        families: Set[str] = set()
        resources: Set[str] = set()

        # Files
        if any(w in ql for w in ("pdf", "document", "file", "folder", "downloads", "documents", "desktop", "txt", "docx", "zip", "mp3", "mp4", "jpg", "png", "duplicate", "organize", "archive")):
            families.add("FILE")
            resources.add("FileResource")

        # Phone / Mobile
        if any(w in ql for w in ("phone", "android", "mobile", "cell", "device")):
            families.add("PHONE")
            resources.add("DeviceResource")

        # App
        if any(w in ql for w in ("app", "application", "program", "software", "chrome", "notepad", "calculator", "calc", "vlc", "spotify", "vscode", "paint", "edge", "firefox", "launch", "kill", "close window")):
            families.add("APP")
            resources.add("ApplicationResource")

        # System audio/display/hardware
        if any(w in ql for w in ("volume", "loudness", "sound", "speaker", "mute", "unmute", "audio", "valume")):
            families.add("SYSTEM")
            resources.add("SystemAudio")
        if any(w in ql for w in ("screenshot", "snapshot", "snip", "screen grab", "capture screen", "capture my screen")):
            families.add("SYSTEM")
            resources.add("SystemScreen")
        if any(w in ql for w in ("brightness", "dim", "brighten", "lights", "backlight")):
            families.add("SYSTEM")
            resources.add("SystemBrightness")
        if any(w in ql for w in ("specs", "hardware", "cpu", "ram", "memory usage", "memory", "battery", "juice", "power", "diagnostics", "audit", "disk space", "tasks")):
            families.add("SYSTEM")
            resources.add("SystemHardware")
        if any(w in ql for w in ("time", "clock", "date", "hour", "day")):
            families.add("SYSTEM")
            resources.add("SystemTime")

        # WhatsApp
        if any(w in ql for w in ("whatsapp", "chat", "unread messages", "message to")):
            families.add("WHATSAPP")
            resources.add("MessageResource")

        # Knowledge / RAG
        if any(w in ql for w in ("news", "rss", "headline", "note", "memo", "summarize", "summary", "briefing", "meeting notes")):
            families.add("RAG")
            resources.add("KnowledgeResource")

        # Browser
        if any(w in ql for w in ("browser", "web", "website", "url", "link", "google search", "search google", "youtube")):
            families.add("BROWSER")
            resources.add("BrowserResource")

        return families, resources

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        category: Optional[CapabilityCategory] = None,
        working_memory: Any = None,
        min_score: float = 0.5,
    ) -> List[Tuple[CapabilityDefinition, float]]:
        """
        Retrieves Top-K candidate capabilities matching the query.
        Splits multi-clause requests to preserve multi-capability coverage.
        Returns ranked list of (CapabilityDefinition, score) tuples.
        """
        cleaned = query.strip().casefold()
        if not cleaned:
            return []

        # Split conjunction clauses for multi-intent requests
        clauses = [c.strip() for c in re.split(r"\s+(?:and\s+then|and|then|after\s+that)\s+|,\s*", cleaned) if len(c.strip()) >= 3]
        if not clauses:
            clauses = [cleaned]

        all_scored: Dict[str, Tuple[CapabilityDefinition, float]] = {}

        for clause in clauses:
            clause_scored = self._retrieve_clause(clause, category=category, working_memory=working_memory)
            for cap, sc in clause_scored:
                if cap.id not in all_scored or sc > all_scored[cap.id][1]:
                    all_scored[cap.id] = (cap, sc)

        results = [item for item in all_scored.values() if item[1] >= min_score]
        if not _PHONE_MENTION.search(cleaned):
            # Phone-only capabilities ("tap Allow on my phone") must never act on a request about the PC.
            results = [item for item in results if not (item[0].target_tool or "").startswith("android_")]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _retrieve_clause(
        self,
        clause: str,
        category: Optional[CapabilityCategory] = None,
        working_memory: Any = None,
    ) -> List[Tuple[CapabilityDefinition, float]]:
        words = re.findall(r"\w+", clause)
        content_tokens = [w for w in words if w not in STOPWORDS]
        norm_tokens = [_stem_and_normalize(t) for t in content_tokens if _stem_and_normalize(t) not in STOPWORDS]
        norm_set = set(norm_tokens)

        inferred_families, inferred_resources = self._infer_families_and_resources(clause)

        # Contextual resource awareness from Working Memory
        if working_memory:
            if hasattr(working_memory, "get_recent_search_results") and working_memory.get_recent_search_results():
                if any(p in clause for p in ("it", "second", "first", "third", "that", "this", "which", "them")) and not any(k in clause for k in ("install", "setup", "download")):
                    inferred_families.add("FILE")
                    inferred_resources.add("FileResource")

            active_topic = getattr(working_memory, "get_active_topic", lambda: None)()
            last_fail = getattr(working_memory, "get_last_failure", lambda: None)()
            if (active_topic or last_fail) and any(p in clause for p in ("install", "setup", "download")):
                inferred_families.add("APP")
                inferred_resources.add("ApplicationResource")
            elif active_topic and any(p in clause for p in ("open it", "run it", "launch it", "close it")):
                inferred_families.add("APP")
                inferred_resources.add("ApplicationResource")

        candidates = self.capabilities
        if category:
            candidates = [c for c in candidates if c.category == category]

        scored: List[Tuple[CapabilityDefinition, float]] = []
        has_number = bool(_NUMBER_WORDS.search(clause))
        is_vol_adjust = has_number or any(w in clause for w in ("up", "down", "increase", "decrease", "raise", "lower", "to", "set"))

        for cap in candidates:
            tok_counts = self.doc_tokens.get(cap.id, Counter())
            cap_norm_set = self.doc_norm_tokens.get(cap.id, set())
            cap_fam = self._get_cap_family(cap)
            score = 0.0

            # 1. BM25 term weighting on content tokens
            for qt in content_tokens:
                if qt in tok_counts:
                    idf = math.log((self.doc_count - self.df[qt] + 0.5) / (self.df[qt] + 0.5) + 1.0)
                    tf = tok_counts[qt]
                    score += idf * (tf / (tf + 1.5))

            # 2. Normalized term overlap boost (semantic recall)
            common_norm = norm_set.intersection(cap_norm_set)
            if common_norm:
                score += len(common_norm) * 4.0

            # 3. Intent Family alignment
            if cap_fam in inferred_families:
                score += 8.0

            # 4. Keyword / Example boosts (keyword patterns are compiled once per capability)
            for kw_clean, kw_re in self._keyword_patterns(cap):
                if kw_clean not in clause:
                    continue  # a whole-word match implies a substring match; skip the regex cheaply
                if len(kw_clean) <= 3:
                    if kw_re.search(clause):
                        score += 8.0
                        break
                elif kw_re.search(clause) or len(kw_clean) > 6:
                    score += 8.0
                    break

            for ex in cap.examples:
                ex_clean = ex.lower().strip()
                if ex_clean == clause or (len(ex_clean) >= 6 and ex_clean in clause):
                    score += 12.0
                    break

            # 5. Counterexample penalty
            for cex in cap.counterexamples:
                cex_clean = cex.lower().strip()
                if cex_clean in clause or (len(cex_clean) > 8 and cex_clean in clause):
                    score -= 15.0

            # 6. Resource type compatibility & domain rules
            if "SystemAudio" in inferred_resources:
                if any(w in clause for w in ("mute", "silence", "quiet")) and "unmute" not in clause:
                    if "volume_mute" in cap.id:
                        score += 25.0
                    elif "volume_set" in cap.id or "volume_get" in cap.id:
                        score -= 10.0
                elif "unmute" in clause:
                    if "volume_unmute" in cap.id:
                        score += 25.0
                elif is_vol_adjust:
                    if "volume_set" in cap.id:
                        score += 25.0
                    elif "volume_get" in cap.id:
                        score -= 10.0
                else:
                    if "volume_get" in cap.id:
                        score += 20.0

            if "SystemScreen" in inferred_resources and "screenshot" in cap.id:
                score += 20.0

            if "SystemBrightness" in inferred_resources and "brightness" in cap.id:
                score += 20.0

            if "SystemHardware" in inferred_resources:
                if "memory" in clause and "top_memory_processes" in cap.id:
                    score += 25.0
                elif "diagnostics" in cap.id or "info" in cap.id:
                    score += 15.0

            if "DeviceResource" in inferred_resources and "FileResource" in inferred_resources:
                if "send_file" in cap.id:
                    score += 22.0
                elif "find" in cap.id:
                    score += 14.0

            # Window management
            is_screenshot_phrase = any(w in clause for w in ("grab", "capture", "snip", "shot", "screenshot", "snapshot"))
            if not is_screenshot_phrase and ("window" in clause or any(w in clause for w in ("minimize", "maximize", "restore", "fullscreen", "full screen", "fulll screen", "max"))):
                if any(w in clause for w in ("close", "kill", "shut", "exit", "dismiss")):
                    if "close_window" in cap.id:
                        score += 25.0
                    elif "close" in cap.id:
                        score += 15.0
                elif "minimize" in clause or "hide" in clause:
                    if "minimize_window" in cap.id:
                        score += 25.0
                elif any(w in clause for w in ("maximize", "enlarge", "fullscreen", "full screen", "fulll screen", "max")):
                    if "maximize_window" in cap.id:
                        score += 25.0
                elif "restore" in clause or "unminimize" in clause:
                    if "maximize_window" in cap.id:
                        score += 20.0
                elif "desktop" in clause:
                    if "show_desktop" in cap.id:
                        score += 25.0
            elif "show desktop" in clause or "minimize all" in clause:
                if "show_desktop" in cap.id:
                    score += 25.0

            # If requesting full screen / maximize window without capture/snip/shot, penalize screenshot
            if any(w in clause for w in ("fullscreen", "full screen", "fulll screen")) and not any(w in clause for w in ("grab", "shot", "capture", "take", "snip", "image", "photo", "save")):
                if "screenshot" in cap.id:
                    score -= 25.0

            # File actions: Search vs Open vs Organize vs List
            if "FileResource" in inferred_resources:
                if any(w in clause for w in ("find", "search", "locate", "look for", "where is", "where did", "where are", "scan")):
                    if "file.find" in cap.id:
                        score += 20.0
                    elif "file.open" in cap.id:
                        score -= 5.0
                elif any(w in clause for w in ("organize", "tidy", "clean up", "sort")):
                    if "organize_downloads" in cap.id:
                        score += 25.0
                elif any(w in clause for w in ("duplicate", "duplicates", "repeated")):
                    if "find_duplicates" in cap.id:
                        score += 25.0
                elif any(w in clause for w in ("list", "contents", "what is in", "show folder", "files in")):
                    if "list_directory" in cap.id:
                        score += 20.0
                elif any(w in clause for w in ("open", "launch", "view", "read", "display")):
                    if "file.open" in cap.id:
                        score += 20.0

            # App Lifecycle: Open vs Close
            if "ApplicationResource" in inferred_resources or any(w in clause for w in ("app", "program", "software", "chrome", "notepad", "calculator", "vlc", "spotify", "vscode", "explorer", "browser")):
                if any(w in clause for w in ("open", "launch", "start", "bring up", "pull up", "run", "fire up")):
                    if "app.open" in cap.id:
                        score += 25.0
                    elif "app.close" in cap.id:
                        score -= 15.0
                elif any(w in clause for w in ("close", "kill", "terminate", "shut", "quit", "exit")):
                    if "app.close" in cap.id or "close_window" in cap.id:
                        score += 25.0
                    elif "app.open" in cap.id:
                        score -= 15.0

            # Location query: "where is ... installed" -> boost get_location, penalize install_software
            if any(w in clause for w in ("where is", "where did", "where was", "location", "path of")):
                if "get_location" in cap.id or "location" in cap.id:
                    score += 25.0
                if "install_software" in cap.id:
                    score -= 20.0

            # Domain mismatch penalties
            if "SystemAudio" in inferred_resources and cap_fam not in ("SYSTEM", "WINDOWS"):
                score -= 15.0
            if "SystemBrightness" in inferred_resources and "brightness" not in cap.id:
                score -= 15.0

            if score >= 0.5:
                scored.append((cap, round(score, 3)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
