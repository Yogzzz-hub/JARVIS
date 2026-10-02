import os
import re
from contextvars import ContextVar
from time import perf_counter_ns
from typing import Any
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.cache import HotRouteCache
from jarvis.core.router.catalog import IntentCatalog
from jarvis.core.router.complexity import check_complexity_gate, check_deterministic_compound
from jarvis.core.router.capability_intents import is_read_action
from jarvis.core.router.control import match_control
from jarvis.core.router.disambiguation import disambiguate_app
from jarvis.core.router.fuzzy import match_fuzzy
from jarvis.core.context.entity_extractor import EntityExtractor
from jarvis.core.context.followup_detector import FollowupDetector
from jarvis.core.context.models import FollowupType, ReferenceConfidence
from jarvis.core.router.guards import check_negation, is_informational_or_question
from jarvis.core.router.matcher import match_patterns
from jarvis.core.router.models import (
    SubCommand,
    ComplexityLevel,
    ReasonCode,
    RouteDecision,
    RouteLane,
    RouteSource,
)
from jarvis.core.router.normalize import clean_for_matching, normalize_text
from jarvis.core.router.ollama import LLMProvider, OllamaProvider

KNOWN_SHELL_COMMANDS = frozenset({
    "dir", "ipconfig", "ping", "systeminfo", "tasklist", "netstat", "hostname",
    "whoami", "echo", "curl", "tree", "get-process", "get-service", "python",
    "node", "pip", "npm", "git", "wmic", "cls", "path", "nslookup", "tracert"
})


_SPOKEN_WORDS = re.compile(r"\b(?:and|say|saying|tell|that|the|to|on|in|my|me|him|her|please|whatsapp|message|text|if|about|"
                           r"is|are|was|what|who|how|why|can|could|would|should|you|i|a|an|for|with|then)\b", re.I)


def _looks_like_shell(text: str) -> bool:
    """'ping google.com', 'ipconfig /all', 'git status' are shell; 'ping keerthi on whatsapp and say hi' is a message."""
    parts = text.split()
    if len(parts) > 6:
        return False
    if parts[0].lower() in ("ping", "tracert", "nslookup") and len(parts) > 1 and \
            not re.search(r"[.:\d]|^localhost$|^-", parts[1], re.I):
        return False  # "ping arun" is a message to Arun, not a network ping
    return not _SPOKEN_WORDS.search(" ".join(parts[1:])) if len(parts) > 1 else True


def _llm_down(decision) -> bool:
    """The classifier failed because Ollama is unreachable (not merely slow or confused)."""
    trace = getattr(decision, "context_trace", None) or {}
    return bool(trace.get("llm_unavailable")) or "AI model unavailable" in (getattr(decision, "clarification", "") or "")

# Per-request flags (context variables, so concurrent requests never see each other's):
_IN_CLAUSE: ContextVar[bool] = ContextVar("router_in_clause", default=False)  # routing one step of a multi-step request
_NO_MODEL: ContextVar[bool] = ContextVar("router_no_model", default=False)    # deterministic lanes only (live preview)
_QUALIFIED: ContextVar[bool] = ContextVar("router_qualified", default=False)  # routing the core of a qualified command


_RUN_UP = re.compile(r"^\W*(?:(?:hey|ok|okay|hi)\s+)?(?:jarvis\W+)?(?:um+|uh+|so)?\W*(?:when(?:ever)?\s+you\s+(?:get|have)\s+a\s+"
                     r"(?:sec(?:ond)?|minute|moment|chance)|if\s+you\s+(?:can|could|don'?t\s+mind)|real\s+quick|quick\s+one|"
                     r"(?:(?:a|one|another|small)\s+)?(?:quick\s+)?question(?:\s+for\s+you)?|quick\s+q)"
                     r"\s*,\s*", re.I)
# "aight jarvis, open krita", also behind a polite / filler / wake lead-in ("could you please yo open up krita")
_SLANG_LEAD = re.compile(r"^\W*(?:(?:could|can|would|will)\s+(?:you|u)\s+(?:please\s+|pls\s+)?|please\s+|pls\s+|kindly\s+|"
                         r"um+\W+|uh+\W+|hmm+\W+|okay\W+|ok\W+|hey\s+jarvis\W+|jarvis\W+)*"
                         r"(?:yo|aight|ayy|yeah|yep|ya|alright)\b[\s,.!]+", re.I)
_TAIL = re.compile(r"(?:[\s,]+(?:for\s+me|please|pls|plz|thanks|thank\s+you|thx|ty|real\s+quick|quick(?:ly)?|right\s+now|"
                   r"(?<!from\s)(?<!till\s)(?<!until\s)(?<!by\s)now|asap|i\s+need\s+it|jarvis|da|bro|buddy)\b)+[\s.!?]*$", re.I)
_CONTENT_LEAD = re.compile(r"^\W*(?:(?:hey|ok|okay|um+|uh+)\s+)?(?:jarvis\W+)?(?:please\s+|kindly\s+|can\s+you\s+|could\s+you\s+"
                           r"(?:please\s+)?)?(?:tell|message|msg|text|send|whats\s*app|reply|respond|say|type|write|dictate|"
                           r"note|remember|remind|e-?mail|mail|draft|search|google|look\s+up|translate|ask|let|post|"
                           r"compose)\b", re.I)
# a later step that carries words ("open notepad and type hello, wait for me"): its tail is content too
_CONTENT_ANY = re.compile(r"(?:,|\band\b|\bthen\b)\s*(?:then\s+)?(?:tell|message|msg|text|send|whats\s*app|reply|say|type|write|dictate|"
                          r"note|remind|e-?mail|search|google|ask|post|compose)\b", re.I)
# "open my project on the PC" (said from the phone or not): this PC is where JARVIS acts by default
_ACT_HERE = re.compile(r"^\W*(?:(?:hey|ok|okay)\s+)?(?:jarvis\W+)?(?:please\s+|can\s+you\s+|could\s+you\s+)?(?:open|launch|start|run|"
                       r"show|play|bring|close|switch|take|make|create|put)\b", re.I)
_ON_THIS_PC = re.compile(r"\s+(?:on|in)\s+(?:my|the|this)\s+(?:pc|computer|laptop)(?=\W*$)", re.I)


class SmartRouter:
    def __init__(
        self,
        catalog: IntentCatalog | None = None,
        llm_provider: LLMProvider | None = None,
        cache: HotRouteCache | None = None,
        app_resolver: Any = None,
        registry_version: str = "v1.0.0",
        trace_debug: bool = False,
        tool_registry: Any = None,
        working_memory: Any = None,
        reference_resolver: Any = None,
        capability_registry: Any = None,
        capability_retriever: Any = None,
    ):
        self.catalog = catalog or IntentCatalog.get_default()
        self.llm_provider = llm_provider or OllamaProvider()
        self.cache = cache or HotRouteCache(capacity=2048)
        self.app_resolver = app_resolver
        self.registry_version = registry_version
        self.trace_debug = trace_debug
        self.total_routed = 0
        self.lane_counts: dict[str, int] = {lane.value: 0 for lane in RouteLane}
        self.tool_registry = tool_registry
        self.working_memory = working_memory
        self.reference_resolver = reference_resolver
        if self.working_memory is None:
            try:
                from jarvis.memory.working_memory import WorkingMemory
                self.working_memory = WorkingMemory()
            except Exception:
                pass
        if self.reference_resolver is None and self.working_memory is not None:
            try:
                from jarvis.core.context.resolver import ReferenceResolver
                self.reference_resolver = ReferenceResolver(self.working_memory)
            except Exception:
                pass
        from jarvis.core.capabilities.registry import get_default_capability_registry
        from jarvis.core.capabilities.retrieval import CapabilityRetriever
        from jarvis.core.capabilities.frame import FrameExtractor
        self.capability_registry = capability_registry or get_default_capability_registry(tool_registry)
        self.capability_retriever = capability_retriever or CapabilityRetriever(self.capability_registry)
        self.frame_extractor = FrameExtractor()
        if hasattr(self.llm_provider, "capability_retriever"):
            self.llm_provider.capability_retriever = self.capability_retriever
        if hasattr(self.llm_provider, "capability_registry"):
            self.llm_provider.capability_registry = self.capability_registry
        if tool_registry is not None and getattr(self.llm_provider, "tool_registry", False) is None:
            self.llm_provider.tool_registry = tool_registry
        self.last_clarification_candidates: list[str] = []
        self.last_clarification_intent: str = "open_app"

    async def preview(self, text: str) -> RouteDecision:
        """Route without any model call: for live previews of a transcript that is still being spoken."""
        token = _NO_MODEL.set(True)
        try:
            return await self.route(text)
        finally:
            _NO_MODEL.reset(token)

    _SEND_INTENTS = ("send_whatsapp_message", "reply_whatsapp_message", "reply_whatsapp_all", "send_whatsapp_bulk",
                     "whatsapp_action", "send_email", "localsend_text")
    _NOT_A_CONTACT = frozenset({"me", "myself", "i", "you", "u", "yourself", "us", "we", "him", "her", "them", "it", "this",
                                "that", "someone", "anyone", "somebody", "everyone", "jarvis", "the", "my", "total", "all",
                                "to", "a", "an", "whatsapp", "message", "msg", "my phone", "phone", "my mobile", "mobile",
                                "the phone", "my pc", "my laptop", "pc", "laptop"})
    _TELL_ME = re.compile(r"^(?:(?:hey\s+)?jarvis\s*,?\s+)?(?:(?:can|could|would)\s+(?:you|u)\s+)?(?:please\s+)?"
                          r"(?:tell\s+me|show\s+me|let\s+me\s+know|give\s+me|find\s+out)\s+(?P<rest>.+)$", re.I)

    @staticmethod
    def _operator_mode() -> str:
        """App family the owner is working in (browser / media / editor / ide / ...), '' when unknown."""
        try:
            from jarvis.core.operator.windows import get_window_tracker
            cur = get_window_tracker().current()
            return cur.family if cur else ""
        except Exception:
            return ""

    async def route(self, request: CommandRequest | str) -> RouteDecision:
        """Route, then sanity-check the result: a message is never addressed to 'me' / 'you' / 'it'."""
        if isinstance(request, str):
            request = CommandRequest(text=request)
        from jarvis.core.router.normalize import repair_swapped_letters
        unswapped = repair_swapped_letters(request.text or "")
        if unswapped != request.text:
            request = request.model_copy(update={"text": unswapped})   # "open the rceycle bin": two letters swapped
        from jarvis.core.router.canonical import canonicalize
        canon = canonicalize(request.text or "")
        if canon != " ".join((request.text or "").split()) and canon.strip():
            request = request.model_copy(update={"text": canon})   # "gimme X", "X is stuck, kill it", "can the volume be 40"
        # Questions about JARVIS itself and control of its own tasks: runtime state only - before retrieval, the
        # planner or any model, so they can never reach an unrelated (e.g. install / delete) capability.
        early = self._domain_first(request)
        if early is not None:   # "git status of jarvis" is about the jarvis repo, not about JARVIS itself
            return self._check_frame_safety(self._semantic_policy(request, self._plausible(request, early)), request.text or "")
        from jarvis.core.router.introspection import match_introspection
        own = match_introspection(request.text or "", request.request_id)
        if own is not None:
            self._record(own)
            return own
        if not re.match(r"^\W*(?:say|announce|shout)\b", request.text or "", re.I):
            loud = re.sub(r"\s+(?:out\s+loud|aloud|loudly)\b", "", request.text or "", flags=re.I)
            if loud != request.text and loud.strip():
                request = request.model_copy(update={"text": loud})   # answers are spoken anyway: "read X out loud"
        lead = _SLANG_LEAD.sub("", request.text or "", count=1)
        if lead != request.text and lead.strip():
            request = request.model_copy(update={"text": lead})     # "aight jarvis, open krita"
        run_up = _RUN_UP.sub("", request.text or "", count=1)
        if run_up != request.text and run_up.strip():
            # "hey jarvis, when you get a sec, switch to the gmail tab": politeness before the command, not a condition
            request = request.model_copy(update={"text": run_up})
        tail = _TAIL.sub("", request.text or "")
        if tail != request.text and re.search(r"[a-z]{2,}", re.sub(r"\b(?:hey|hi|ok|okay|um+|uh+|hmm+|so|jarvis|quick|question|could|can|would|will|you|u|please|pls|kindly)\b",
                                                                 "", tail.lower())) \
                and not _CONTENT_LEAD.match(request.text or "") and not _CONTENT_ANY.search(request.text or ""):
            # "open krita for me real quick", "pls set brightness 60 thx": courtesy and urgency, not part of the
            # command. Never stripped from a message, note or search - there the words belong to the content.
            request = request.model_copy(update={"text": tail})
        try:  # Thanglish word order -> the English command ("chrome open pannu" -> "open chrome")
            from jarvis.core.multilingual import to_english_command
            from jarvis.core.router.normalize import correct_command_typos
            english = to_english_command(request.text or "")
            if english == request.text:  # "vloume konjam kammi pannu": a typo in the English word
                fixed = to_english_command(correct_command_typos(" ".join((request.text or "").lower().split())))
                english = fixed if fixed != correct_command_typos(" ".join((request.text or "").lower().split())) else english
            if english != request.text:
                request = request.model_copy(update={"text": english})
        except Exception:
            pass
        dashed = re.sub(r"\s*[\u2014\u2013]\s*", ", ", request.text or "")     # "use Chrome—actually Edge"
        # "set my laptop sound to 40": the device's own sound / brightness is the volume / brightness
        dashed = re.sub(r"\b(?:my|the|this)\s+(?:laptop|pc|computer|system|desktop|speaker|device)(?:'s)?\s+"
                        r"(sound|volume|brightness|screen\s+brightness|display\s+brightness)\b", r"the \1", dashed, flags=re.I)
        if dashed != request.text and dashed.strip():
            request = request.model_copy(update={"text": dashed})
        # one constraint representation for the request: a corrected value is superseded before any matcher sees it
        # ("message Ramesh I'll be late - no, message Rajesh"), a prohibited clause is kept as a constraint and not routed
        # ("don't pay anything, just read me the cart total")
        from jarvis.core.semantics.constraints import apply_correction, prohibitions
        corrected, superseded = apply_correction(request.text or "")
        if superseded and corrected.strip():
            request = request.model_copy(update={"text": corrected})
        positive, prohibited = prohibitions(request.text or "")
        if prohibited:
            request = request.model_copy(update={"text": canonicalize(positive) or positive})
        if not re.search(r"\b(?:phone|mobile|android)\b", request.text or "", re.I) and _ACT_HERE.match(request.text or ""):
            here = _ON_THIS_PC.sub("", request.text or "")
            if here != request.text and len(here.split()) >= 2:
                request = request.model_copy(update={"text": here})
        texts = self.__dict__.setdefault("routed_texts", {})
        texts[request.request_id] = request.text or ""
        while len(texts) > 64:
            texts.pop(next(iter(texts)))
        said = self._discourse(request)
        if said is not None:
            said = self._semantic_policy(request, said)
            self._record(said)
            return said
        decision = self._domain_first(request) or await self._route(request)
        decision = await self._tell_me(request, decision)
        decision = self._sanity(decision, request.text or "")
        decision = await self._last_clause(request, decision)
        decision = self._check_recipient(decision, request.text or "")
        decision = self._vague(request, decision)
        if decision.intent != "clarify":
            decision = await self._qualified(request, decision)
        decision = self._plausible(request, decision)
        decision = self._broad_scope(request, decision)
        decision = self._constraints(request, decision, prohibited)
        return self._check_frame_safety(self._semantic_policy(request, decision), request.text or "")

    _PROHIBITED_EFFECT = {
        "pay": "payment", "buy": "payment", "purchase": "payment", "order": "payment", "checkout": "payment",
        "delete": "destroy", "remove": "destroy", "erase": "destroy", "trash": "destroy", "uninstall": "destroy", "wipe": "destroy",
        "send": "message", "message": "message", "text": "message", "reply": "message", "forward": "message", "share": "message",
        "email": "message", "post": "message", "open": "open", "launch": "open", "start": "open", "close": "close", "quit": "close",
        "kill": "close", "install": "install", "call": "call", "dial": "call", "ring": "call", "click": "ui", "tap": "ui",
        "press": "ui", "submit": "ui", "type": "type", "shut": "power", "restart": "power", "reboot": "power", "lock": "power",
    }
    _EFFECT_TOOLS = {
        "payment": {"browser_click", "ui_op", "screen_click", "web_task", "computer_task", "desktop_ui_click", "browser_autofill"},
        "destroy": {"delete_file", "uninstall_software", "empty_recycle_bin", "batch_rename", "powershell_command"},
        "message": {"send_whatsapp_message", "send_whatsapp_bulk", "reply_whatsapp_message", "reply_whatsapp_all", "gmail_create_draft",
                    "localsend_text", "localsend_file", "deliver_op"},
        "open": {"open_app", "open_website", "open_file", "android_open_app"}, "close": {"close_app"},
        "install": {"install_software", "android_install_apk"}, "call": {"android_dial", "phone_op"},
        "ui": {"browser_click", "ui_op", "screen_click", "desktop_ui_click"}, "type": {"dictate_text", "type_text", "browser_type"},
        "power": {"system_power_control", "system_op"},
    }
    _CONTENT_KEYS = ("message", "text", "instruction", "query", "fact", "content", "summary", "request")
    _EXCLUSION_KEYS = ("target", "except", "exclude", "keep", "app")

    def _constraints(self, request: CommandRequest, decision: RouteDecision, prohibited: list[str]) -> RouteDecision:
        """Negative constraints survive routing: a prohibited effect never runs, and an exclusion ("except Arun", "not the
        13th one") is carried into the tool or the target - never left inside a message, never silently dropped."""
        if decision.lane not in (RouteLane.LANE_0, RouteLane.LANE_1) or not decision.intent:
            return decision
        tools = [s.tool for s in decision.subcommands] or [decision.intent]
        targets = " ".join(str(v) for s in (decision.subcommands or []) for v in (s.arguments or {}).values()) \
            + " " + " ".join(str(v) for v in (decision.slots or {}).values())
        for p in prohibited:
            verb = (re.match(r"[a-z]+", p.lower()) or [""])[0]
            effect = self._PROHIBITED_EFFECT.get(verb)
            obj = re.sub(r"^\S+\s+(?:(?:the|my|a|an)\s+)?", "", p.lower(), count=1).strip()
            generic = not obj or re.fullmatch(r"(?:it|that|this|them|anything|everything|any\s+\w+|yet|now|it\s+yet)", obj)
            # "don't open spotify, open chrome": only Spotify is prohibited; "don't pay anything": any payment is
            if effect and set(tools) & self._EFFECT_TOOLS.get(effect, set()) and (generic or obj in targets.lower()):
                return self._decision(request, RouteLane.REJECT, None, {"prohibited": p},
                                      f"You asked me not to {p}, so I won't.", ReasonCode.NEGATED_ACTION)
        from jarvis.core.semantics.constraints import extract_exclusions
        positive, excluded = extract_exclusions(request.text or "")
        if not excluded:
            return decision
        slots = dict(decision.slots or {})
        reflected = any(x.lower() in str(slots.get(k) or "").lower() for k in self._EXCLUSION_KEYS for x in excluded)
        for k in self._CONTENT_KEYS:   # "I'm busy, except Arun" is not the message to everyone
            v = slots.get(k)
            if isinstance(v, str) and any(x.lower() in v.lower() for x in excluded):
                slots[k] = extract_exclusions(v)[0].rstrip(" ,;")
        if decision.intent == "reply_whatsapp_all":
            slots["exclude"] = excluded
            return decision.model_copy(update={"slots": slots})
        if decision.intent == "delete_file" and slots.get("path"):
            from jarvis.core.semantics.resources import parse_path_ref, resolve_target
            ref = parse_path_ref(re.sub(r"[\\/]+", "/", str(slots["path"])).split("/")[-1] if os.path.isabs(str(slots["path"])) else str(slots["path"]))
            res = resolve_target(ref, exclude=excluded)
            if res.status == "found":
                slots["path"] = str(res.path)
            elif res.status == "ambiguous":
                return self._decision(request, RouteLane.CLARIFY, "delete_file", {}, "Which one exactly? I found: "
                                      + ", ".join(c.name for c in res.candidates[:4]), ReasonCode.MISSING_REQUIRED_SLOT)
            return decision.model_copy(update={"slots": slots})
        if decision.intent in ("show_desktop", "minimize_all", "minimize_all_windows") or (decision.intent == "window_op"
                                                                                           and slots.get("action") in ("minimize_all", "show_desktop")):
            # "minimise everything except vs code": keep that one, minimise the rest
            return decision.model_copy(update={"intent": "window_op", "slots": {"action": "isolate", "target": excluded[0]}})
        _TIME = r"(?:morning|evening|night|day|days|week|weeks|weekday|weekdays|weekend|month|hour|hours|minute|minutes|time|times|year|" \
                r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        universal = re.search(rf"\b(?:everything|every\s*one|everybody|all|every|each|whole)\b(?!\s+(?:the\s+)?{_TIME}\b)", positive, re.I)
        if universal and not reflected:
            # a set-wide action that cannot leave the excluded one out must not run without it
            return self._decision(request, RouteLane.CLARIFY, decision.intent, {},
                                  f"I can't leave out {', '.join(excluded)} with that in one go - tell me what exactly to do.",
                                  ReasonCode.MISSING_REQUIRED_SLOT)
        return decision.model_copy(update={"slots": slots})

    _CONSEQUENTIAL_EFFECTS = frozenset({"delete_file", "move_file", "rename_file", "batch_rename", "uninstall_software",
                                        "empty_recycle_bin", "install_software", "update_software", "system_power_control",
                                        "close_app", "send_whatsapp_message", "send_whatsapp_bulk", "reply_whatsapp_message",
                                        "reply_whatsapp_all", "gmail_create_draft", "localsend_file", "localsend_text",
                                        "android_push_file", "calendar_create_event", "powershell_command", "system_op"})

    def _semantic_policy(self, request: CommandRequest, decision: RouteDecision) -> RouteDecision:
        """The request's domain and risk decide what may run, whatever tool the words matched (Blind-11: a payment became
        a WhatsApp message, a PIN became a stored fact, "format my C drive ... fresh" opened an app called "fresh").
        A must-never request is refused on every lane, the planner included; a question about it is answered."""
        if decision.lane in (RouteLane.REJECT, RouteLane.CONTROL) or decision.reason_code == ReasonCode.QUESTION_NOT_COMMAND:
            return decision
        from jarvis.core.semantics.policy import check
        if decision.subcommands:
            tools = [s.tool for s in decision.subcommands]
        elif decision.lane in (RouteLane.LANE_0, RouteLane.LANE_1):
            tools = [decision.intent]
        else:
            tools = [None]   # a clarification, an answer or the planner: whatever it would become
        verdict = check(tools, request.text or "", self._CONSEQUENTIAL_EFFECTS)
        if verdict is None:
            return decision
        if verdict["kind"] == "chat":
            return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.7,
                                 source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.SIMPLE,
                                 normalized_text=decision.normalized_text, reason_code=ReasonCode.QUESTION_NOT_COMMAND)
        return self._decision(request, RouteLane.REJECT, None, {"refused": verdict["reason"]}, verdict["question"],
                              ReasonCode.POLICY_BLOCKED)

    _DEFINITION_Q = re.compile(
        r"^(?:(?:hey\s+)?jarvis\s*,?\s*)?(?:what(?:'s|\s+is|\s+are)\s+(?:a|an|the\s+point\s+of|meant\s+by)\b|which\s+.{1,40}\s+(?:is|are)\s+"
        r"(?:the\s+)?(?:best|better|good|worse|fastest|safest)\b|how\s+(?:does|do|did|can|could|would|is|are)\b|why\s+(?:is|are|do|does|did|would)\b|"
        r"explain\b|tell\s+me\s+about\b|what\s+do\s+you\s+think\b|let'?s\s+(?:talk|chat|play|discuss)\b|talk\s+to\s+me\b|"
        r"(?:what|which)\s+(?:time|language|languages)\s+do\s+you\b|(?:give|tell)\s+me\s+(?:\d+\s+|some\s+|a\s+few\s+|an?\s+)?"
        r"(?:ideas?|tips?|advice|suggestions?|reasons?|examples?|facts?|jokes?|stor(?:y|ies)|quotes?|opinions?)\b|"
        r"(?:give|tell)\s+me\s+(?:some\s+)?(?:medical|legal|financial|career)\s+advice\b)", re.I)
    _QUESTION = re.compile(r"^(?:(?:hey\s+)?jarvis\s*,?\s*)?(?:what|which|who|whom|whose|why|how|when|where|is|are|was|were|do|does|did|"
                           r"can|could|should|would|will)\b", re.I)

    def _retrieval_ok(self, tool: str, text: str) -> bool:
        """Scoring alone never turns a question into an action: a definition or opinion question ("what's a browser
        cookie", "which browser is best", "give me 3 startup ideas") reaches no tool at all, and any other question only
        a read-only one."""
        if self._DEFINITION_Q.match(text or ""):
            return False
        if self._QUESTION.match(text or "") and not (self._is_read_only(tool) or tool in self._INFO_TOOLS
                                                       or re.match(r"(?:get|list|read|check|find|search|show|recall|recent|command)_", tool)):
            return False
        return True

    _INFO_TOOLS = frozenset({"recent_actions", "command_history", "battery_status", "system_info", "network_info", "get_time",
                             "calendar_list_events", "gmail_list_recent", "read_whatsapp_messages", "list_reminders",
                             "describe_screen", "resource_usage", "task_status", "previous_outcome", "recall_facts"})

    def _broad_scope(self, request: CommandRequest, decision: RouteDecision) -> RouteDecision:
        """'delete all my files and then shut down', 'wipe everything': a destructive verb whose object is everything never
        reaches the planner or a tool - whichever path the sentence took, it is asked about first."""
        from jarvis.core.router.scope import broad_in_text
        if decision.lane in (RouteLane.REJECT, RouteLane.CLARIFY, RouteLane.CONTROL) or decision.intent == "standing_rule":
            return decision
        if decision.intent == "dictate_text" or (decision.slots or {}).get("literal"):
            return decision   # "type literally delete all files": words to type are data, never a command
        text = request.text or ""
        if decision.lane == RouteLane.LANE_2 and decision.needs_planner and self._DEFINITION_Q.match(clean_for_matching(text) or text):
            # "what's a good name for a chatbot app", "explain how vpn works": answered, never planned as a task
            return decision.model_copy(update={"needs_planner": False, "reason_code": ReasonCode.QUESTION_NOT_COMMAND,
                                               "complexity": ComplexityLevel.SIMPLE})
        text = request.text or ""
        if decision.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and not decision.subcommands \
                and re.match(r"(?:(?:hey\s+)?jarvis\s*,?\s*)?what(?:'s|\s+is|\s+are)\s+(?:a|an)\s+[a-z]", clean_for_matching(text) or text, re.I):
            # "what's a browser cookie": a question about a kind of thing is answered, never that thing's tool run
            return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.7,
                                 source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.SIMPLE,
                                 normalized_text=decision.normalized_text, reason_code=ReasonCode.QUESTION_NOT_COMMAND)
        if broad_in_text(text) and not re.search(r"\b(?:don'?t|do\s+not|never)\b", text, re.I):
            return self._decision(request, RouteLane.CLARIFY, None, {}, "That would touch everything, not one thing - I won't do "
                                  "that in one go. Tell me exactly what (which folder, which type) and I'll show you first.",
                                  ReasonCode.MISSING_REQUIRED_SLOT)
        return decision

    @staticmethod
    def _file_subject(text: str) -> str:
        """The name words of a typed file search, without the verb, determiners and type words."""
        t = text.lower().strip(" .?!")
        m = re.search(r"\b[a-z0-9][\w-]*\.[a-z][a-z0-9]{1,4}\b", t)
        if m:
            return m.group(0)
        t = re.sub(r"^(?:please\s+)?(?:find|search\s+for|search|look\s+for|locate|where\s+is|where's|show(?:\s+me)?|get|open)\s+", "", t)
        words = [w for w in t.split() if w not in (
            "my", "the", "a", "an", "all", "any", "some", "that", "this", "those", "these", "me", "for", "file", "files",
            "document", "documents", "doc", "docs", "pdf", "pdfs", "excel", "spreadsheet", "spreadsheets", "sheet", "sheets",
            "word", "image", "images", "photo", "photos", "picture", "pictures", "pic", "pics", "video", "videos", "ppt",
            "powerpoint", "presentation", "presentations", "slides", "zip", "archive", "audio", "song", "songs", "csv",
            "text", "txt", "png", "jpg", "jpeg", "docx", "xlsx", "pptx", "mp3", "mp4")]
        if any(w in ("from", "in", "on", "since", "before", "after", "last", "this", "today", "yesterday", "older", "newer",
                     "bigger", "larger", "smaller", "modified", "created", "edited", "recent", "latest", "new", "old",
                     "than", "between", "except", "not", "without", "under", "over") for w in words):
            return ""   # a time, size or place constraint, not a name: leave it to the constraint search
        return " ".join(words) if words and len(words) <= 4 else ""

    def _domain_first(self, request: CommandRequest) -> RouteDecision | None:
        """Single-capability requests whose details are spelled out ("emails from my manager", "git status of jarvis",
        "reply to divya with ok done"): matched before the broader matchers can take the words for something else.
        Negated and multi-step sentences are left to the full pipeline."""
        text = request.text or ""
        if _IN_CLAUSE.get() or re.search(r"\b(?:don'?t|do\s+not|never|and|then|after\s+that|also)\b|,", text, re.I):
            return None
        from jarvis.core.router.capability_intents import _domains
        lowered = " ".join(text.lower().split()).strip(" .?!")
        lowered = re.sub(r"^(?:(?:hey|ok|okay|hi)\s+)?jarvis\s*[,.!:]?\s+|^(?:um+|uh+|hmm+|ok|okay|so|please|pls)\s*,?\s+", "", lowered)
        if self._DEFINITION_Q.match(lowered):
            return None   # "what's a browser cookie": a question about a thing, never that thing's tool
        d = None
        for candidate in dict.fromkeys((lowered, (clean_for_matching(text) or text).lower().strip(" .?!"))):
            try:
                d = _domains(candidate, text, request.request_id, "")
            except Exception:
                d = None
            if d is not None:
                break
        if d is not None:
            self._record(d)
        return d

    def _carried_over(self, text: str) -> str | None:
        """A short follow-up ("make it 60", "do the same for paint", "close the first one") as the full command it
        stands for, built from the last commands this conversation ran. Not while JARVIS is waiting for an answer."""
        from jarvis.core.context.carryover import carryover_of
        co = carryover_of(self.working_memory)
        if co is None or not co.turns:
            return None
        last = co.turns[-1]
        for getter in ("get_pending_clarification", "get_pending_confirmation"):
            pending = getattr(self.working_memory, getter, lambda: None)()
            if pending is not None and getattr(pending, "created_at", 0) >= last.wall:
                return None
        try:
            full = co.rewrite(text)
        except Exception:
            return None
        return full if full and full.lower() != " ".join(text.lower().split()) else None

    def _plausible(self, request: CommandRequest, decision: RouteDecision) -> RouteDecision:
        """The matched tool must act on a real target: a control is not an app, a question about a document's content
        is not a file search, "the screenshot" is not a file name. Re-route, resolve, plan or ask - never guess."""
        if decision.lane not in (RouteLane.LANE_0, RouteLane.LANE_1) or not decision.intent:
            return decision
        from jarvis.core.router.targets import check_target, verb_mismatch
        text = request.text or ""
        norm = decision.normalized_text or ""
        verdicts = [check_target(s.tool, s.arguments, text, norm) for s in decision.subcommands] if decision.subcommands \
            else [check_target(decision.intent, decision.slots or {}, text, norm)]
        if not decision.subcommands and verb_mismatch(text, decision.intent, self._is_read_only(decision.intent)):
            # "create a calendar event using the time in that email" never ends at a read-only tool (get_time)
            verdicts.append({"kind": "planner", "reason": "the verb asks for a change the matched tool cannot make"})
        if not decision.subcommands and decision.intent in ("find_file", "search_notes", "knowledge_search", "list_directory",
                                                            "document_qa", "search_web") \
                and any(m.group(1).lower() not in ("find", "search", "look up", "check", "show", "read", "open")
                        for m in re.finditer(rf"(?:,|\band\b|\bthen\b)\s*(?:then\s+)?({self._STEP_VERBS}|summari[sz]e|compare|"
                                             rf"prepare|attach|bring\s+back|copy|paste)\b", text, re.I)):
            # "find my latest PDF, copy its summary and paste it ...": one look-up tool cannot do the other steps
            verdicts.append({"kind": "planner", "reason": "several steps for a single look-up tool"})
        if decision.subcommands:   # 'it' after the first step is that step's result: the planner links the steps
            verdicts = [{"kind": "planner"} if (v and v.get("pronoun") and i > 0) else v for i, v in enumerate(verdicts)]
        verdict = next((v for v in verdicts if v), None)
        if verdict is None:
            return decision
        if verdict["kind"] == "rematch" and not decision.subcommands:
            # the frame read it as a file search, but the object is a message: the object-first matchers decide
            from jarvis.core.router.discourse import split_qualifiers
            from jarvis.core.router.extended import match_extended
            token = _IN_CLAUSE.set(True)
            try:  # without its trailing conditions ("..., but don't respond"), and without "show me / tell me"
                core = clean_for_matching(split_qualifiers(text)[0]) or split_qualifiers(text)[0]
                again = match_extended(core, request.request_id)
                asked = self._TELL_ME.match(core.strip())
                if (again is None or again.intent == decision.intent) and asked:
                    again = match_extended(asked.group("rest"), request.request_id)
            finally:
                _IN_CLAUSE.reset(token)
            if again is not None and again.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and again.intent \
                    and again.intent != decision.intent:
                quals = (decision.slots or {}).get("qualifiers")
                return again.model_copy(update={"slots": {**(again.slots or {}), **({"qualifiers": quals} if quals else {})}})
            verdict = {"kind": "planner"}
        quals = (decision.slots or {}).get("qualifiers")
        if verdict["kind"] == "chat":
            # "write my college assignment": something to compose, answered by the assistant, never typed into a window
            return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.7,
                                 source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.SIMPLE,
                                 normalized_text=decision.normalized_text, reason_code=ReasonCode.QUESTION_NOT_COMMAND)
        if verdict["kind"] == "refuse":
            # a security check, a payment or a lock screen: never done for the owner, in any step of the sentence
            return self._decision(request, RouteLane.REJECT, None, {"refused": verdict.get("reason", "unsafe_action")},
                                  verdict["question"], ReasonCode.EXACT_PATTERN)
        if verdict["kind"] == "clarify" and verdict.get("hard"):
            # the scope or target of a consequential step is unclear: ask about the whole sentence, never plan around it
            return self._decision(request, RouteLane.CLARIFY, decision.intent if not decision.subcommands else None, {},
                                  verdict["question"], ReasonCode.MISSING_REQUIRED_SLOT)
        if verdict["kind"] == "reroute" and not decision.subcommands:
            slots = dict(verdict["slots"])
            if quals:
                slots["qualifiers"] = quals
            return decision.model_copy(update={"intent": verdict["intent"], "slots": slots})
        if verdict["kind"] == "clarify" and not decision.subcommands:
            return self._decision(request, RouteLane.CLARIFY, decision.intent, {k: v for k, v in (decision.slots or {}).items()
                                                                               if k not in ("name", "path", "query")},
                                  verdict["question"], ReasonCode.MISSING_REQUIRED_SLOT)
        return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_2, intent=None,
                             slots={"qualifiers": quals} if quals else {}, confidence=0.6, source=RouteSource.COMPLEXITY_GATE,
                             complexity=ComplexityLevel.COMPLEX, needs_planner=True, normalized_text=decision.normalized_text,
                             reason_code=ReasonCode.MULTI_STEP)

    def _decision(self, request: CommandRequest, lane: RouteLane, intent: str | None, slots: dict | None = None,
                  clarification: str | None = None, reason: ReasonCode = ReasonCode.EXACT_PATTERN) -> RouteDecision:
        return RouteDecision(request_id=request.request_id, lane=lane, intent=intent, slots=slots or {}, confidence=0.95,
                             source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE,
                             normalized_text=(request.text or "").strip().lower(), clarification=clarification,
                             reason_code=reason, candidate_count=1, routing_ms=0.0)

    def _discourse(self, request: CommandRequest) -> RouteDecision | None:
        """Sentence shapes decided before any intent matching: a permission claimed by content (refused), a standing
        rule for the future (kept, not executed now) and the owner's list of rules."""
        from jarvis.core.router import discourse
        text = request.text or ""
        if discourse.borrowed_authority(text):
            return self._decision(request, RouteLane.REJECT, None, {"refused": "borrowed_authority"},
                                  discourse.BORROWED_AUTHORITY_REPLY, ReasonCode.NEGATED_ACTION)
        if discourse.OVERRIDE_RULES.search(text.lower()):
            return self._decision(request, RouteLane.REJECT, None, {"refused": "override_rules"},
                                  "My safety rules stay on - nobody can switch them off with a sentence. I haven't done "
                                  "anything. Tell me the one thing you want, and I'll do it the normal way.",
                                  ReasonCode.NEGATED_ACTION)
        low = " ".join(clean_for_matching(text).lower().split()).strip(" .!")
        if discourse.RULES_LIST.match(low) or discourse.RULES_CLEAR.match(low):
            return self._decision(request, RouteLane.LANE_0, "standing_rules",
                                  {"action": "clear" if discourse.RULES_CLEAR.match(low) else "list"})
        from jarvis.core.router.meta_policy import match_meta_policy
        if match_meta_policy(text, request.request_id) is not None:
            return None  # reporting / response policies ("keep replies short") have their own CONTROL handler
        rule = discourse.standing_rule(text)
        if rule is not None:
            return self._decision(request, RouteLane.LANE_0, "standing_rule", rule)
        return None

    async def _qualified(self, request: CommandRequest, decision: RouteDecision) -> RouteDecision:
        """'install ollama, but stop for any administrator approval': route the command without its conditions when
        the conditions got in the way (swallowed into a name, or nothing matched), and keep them as slots."""
        if _IN_CLAUSE.get() or _QUALIFIED.get():
            return decision
        from jarvis.core.router.discourse import slot_has_qualifier, split_qualifiers
        core, quals = split_qualifiers(request.text or "")
        if not quals:
            return decision
        strong = decision.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and bool(decision.intent)
        qwords = set(re.findall(r"[a-z']+", quals["qualifier"].lower()))
        body = str((decision.slots or {}).get("message") or (decision.slots or {}).get("text") or "").lower()
        if strong and body and (decision.intent in self._SEND_INTENTS or decision.intent in ("dictate_text", "set_reminder")) \
                and " ".join(qwords) and all(w in body.split() for w in qwords):
            return decision   # "send kavya on the way": the words are the message, not a condition on sending it

        def leaked(v) -> bool:  # "use the result I opened earlier rather than repeating the search" -> query "than repeating..."
            w = re.findall(r"[a-z']+", v.lower()) if isinstance(v, str) else []
            return len(w) >= 2 and sum(x in qwords for x in w) / len(w) >= 0.6
        contaminated = strong and (slot_has_qualifier(decision.slots or {})
                                   or any(leaked((decision.slots or {}).get(k)) for k in ("name", "query", "path", "message", "target", "text")))
        if strong and not contaminated:
            return decision.model_copy(update={"slots": {**(decision.slots or {}), "qualifiers": quals}})
        negated = decision.lane == RouteLane.REJECT and decision.reason_code == ReasonCode.NEGATED_ACTION
        if not (contaminated or negated or decision.lane in (RouteLane.LANE_2, RouteLane.CLARIFY)):
            return decision
        token = _QUALIFIED.set(True)
        try:
            inner = await self.route(request.model_copy(update={"text": core}))
        finally:
            _QUALIFIED.reset(token)
        # Without its conditions the command must still be safe to take as said: a read-only answer, a step the owner
        # asked to approve first, or the same tool that already matched (only its name / query is cleaned).
        safe = contaminated or self._is_read_only(inner.intent or "") or quals.get("require_approval") or quals.get("preview")
        if not contaminated and (len(self._split_steps(core)) > 1
                                 or re.search(rf"(?:,|\band\b|\bthen\b)\s*(?:then\s+)?(?:{self._STEP_VERBS}|list|compare|tell|give|run|"
                                              rf"execute|attach|summari[sz]e|translate|explain)\b", core, re.I)):
            safe = False  # "find the scripts, list them": several steps - the planner reads them with their conditions
        usable = inner.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and bool(inner.intent) and bool(safe) \
            and not (inner.subcommands and not contaminated) \
            and not any(v[:4] in (inner.intent or "") for v in quals.get("constraints", []) if len(v) >= 4)
        if usable:
            return inner.model_copy(update={"request_id": request.request_id,
                                            "slots": {**(inner.slots or {}), "qualifiers": quals}})
        if inner.lane == RouteLane.CLARIFY and inner.intent and inner.clarification:
            slots = {**(inner.slots or {}), "qualifiers": quals} if quals else (inner.slots or {})
            return inner.model_copy(update={"request_id": request.request_id, "slots": slots})
        if contaminated:  # the matched tool would act on a condition as if it were a name: let the planner read it
            return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_2, intent=None, slots={"qualifiers": quals},
                                 confidence=0.6, source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.COMPLEX,
                                 needs_planner=True, normalized_text=decision.normalized_text, reason_code=ReasonCode.MULTI_STEP)
        return decision

    def _vague(self, request: CommandRequest, decision: RouteDecision) -> RouteDecision:
        """'use the thing from yesterday and send it to him': nothing concrete to act on - ask instead of guessing.
        A matched tool that only had a pronoun to go on ("make this like the previous one" -> media 'previous') is
        asked about too."""
        if _IN_CLAUSE.get():
            return decision
        leaning = decision.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and bool((decision.slots or {}).get("pronoun"))
        if decision.lane not in (RouteLane.LANE_2, RouteLane.CLARIFY) and not leaning:
            return decision
        from jarvis.core.router.discourse import vague_request
        question = vague_request(request.text or "")
        if not question:
            return decision
        return self._decision(request, RouteLane.CLARIFY, "clarify", {}, question, ReasonCode.LOW_CONFIDENCE)

    async def _tell_me(self, request: CommandRequest, decision: RouteDecision) -> RouteDecision:
        """'tell me how many unread messages I have' asks for information: route what comes after 'tell me'.
        Used when the whole sentence found nothing better (chat / planner / clarify) or found a message send."""
        m = self._TELL_ME.match(clean_for_matching(request.text or "").strip())
        if not m or _IN_CLAUSE.get():
            return decision
        weak = decision.lane in (RouteLane.LANE_2, RouteLane.CLARIFY) or decision.intent in (None, "chat", "quick_answer") \
            or decision.intent in self._SEND_INTENTS
        if not weak:
            return decision
        rest = m.group("rest").strip()
        if len(rest.split()) < 2 or re.match(r"^(?:about|a\s+(?:joke|story|fact)|something)\b", rest, re.I):
            return decision  # "tell me about X" / "tell me a joke" are conversation
        token = _NO_MODEL.set(True)
        try:
            inner = await self._route(request.model_copy(update={"text": rest}))
        finally:
            _NO_MODEL.reset(token)
        # only information comes back from "tell me ...": a read-only answer, never an action on the PC, and never
        # a definition question ("tell me what notepad is used for" is conversation, not close/open notepad)
        definitional = re.search(r"\b(?:mean|means|meaning|used\s+for|use\s+of|is\s+for|stands?\s+for|difference|"
                                 r"how\s+(?:does|do|to)|why)\b", rest, re.I)
        if (inner.lane == RouteLane.LANE_0 and inner.intent and inner.intent not in self._SEND_INTENTS
                and not definitional and self._is_read_only(inner.intent)):
            inner.request_id = request.request_id
            return inner
        if decision.intent in self._SEND_INTENTS:  # "tell me <something>" is never a message to someone called "me"
            return RouteDecision(request_id=request.request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.6,
                                 source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.SIMPLE,
                                 normalized_text=decision.normalized_text, reason_code=ReasonCode.QUESTION_NOT_COMMAND)
        return decision

    _READ_ONLY_CACHE: frozenset[str] | None = None

    def _is_read_only(self, intent: str) -> bool:
        if self._READ_ONLY_CACHE is None:
            try:
                ro = {c.target_tool for c in self.capability_registry.list_all()
                      if str(getattr(c.risk_level, "value", c.risk_level)).upper() == "READ_ONLY"}
            except Exception:
                ro = set()
            type(self)._READ_ONLY_CACHE = frozenset(ro | {"read_whatsapp_messages", "summarize_whatsapp_messages", "get_time",
                                                         "battery_status", "network_info", "recent_actions", "quick_answer"})
        return intent in self._READ_ONLY_CACHE

    # "do" is only a question with a subject after it ("do i have...", "do my files..."); "do auto reply" is a command
    _STATE_QUESTION = re.compile(r"^(?:(?:um+|uh+|hey|jarvis|so|wait)\s*,?\s+)*(?:is|are|was|were|does|did|has|have|should|am|isn'?t|doesn'?t|"
                                 r"do(?=\s+(?:i|you|u|we|they|he|she|it|my|your|our|their|his|her|these|those|any|all|people)\b))\b"
                                 r"(?!\s+(?:not|n't)\b)", re.I)

    def _sanity(self, decision: RouteDecision, text: str) -> RouteDecision:
        """Last check on an action: a question about a thing never changes it ("is spotify a good app" does not close
        Spotify), and stored memories are only forgotten when the owner says "forget ..."."""
        if decision.lane not in (RouteLane.LANE_0, RouteLane.LANE_1) or not decision.intent or _IN_CLAUSE.get():
            return decision
        chat = lambda: RouteDecision(request_id=decision.request_id, lane=RouteLane.LANE_2, intent=None, slots={},  # noqa: E731
                                     confidence=0.6, source=decision.source, complexity=ComplexityLevel.SIMPLE,
                                     normalized_text=decision.normalized_text, reason_code=ReasonCode.QUESTION_NOT_COMMAND)
        clean = clean_for_matching(text).strip().lower()
        # "I need python 3.12 is open": a sentence is never an app name to open or close
        app = str((decision.slots or {}).get("name") or (decision.slots or {}).get("app") or "").strip().lower()
        if decision.intent in ("open_app", "close_app") and (re.match(r"(?:i|we|my|me)\b", app)
                                                            or len(app.split()) > 5):
            return chat()
        if decision.intent == "forget_fact" and not re.match(r"^(?:please\s+|(?:can|could|would|will)\s+you\s+(?:please\s+)?)?(?:forget|delete|remove|erase|clear|wipe)\b",
                                                          clean):
            return chat()
        looks_up = re.match(r"^(?:read|list|find|search|get|check|show|recall|summari[sz]e|diagnose|describe|project)_", decision.intent) or \
            decision.intent.endswith(("_status", "_info", "_history", "_events", "_recent", "_actions", "_answer", "_processes", "_logs", "_diff")) or \
            decision.intent in ("get_time", "quick_answer", "wifi_status", "contact_info", "knowledge_search", "document_qa",
                                "morning_briefing", "personal_briefing", "android_notifications", "volume_get", "brightness_get",
                                "project_logs", "project_discover", "database_status", "git_diff", "code_search",
                                "explain_route") or \
            is_read_action(decision.intent, decision.slots or {})  # operator reads: "is antigravity done"
        if self._STATE_QUESTION.match(clean) and not looks_up and not self._is_read_only(decision.intent):
            return chat()
        return decision

    _REMARK_THEN_COMMAND = re.compile(r"^(?P<remark>[^,]{3,80}),\s*(?:(?:and|so|then|please|just|quickly|now)\s+)*(?P<cmd>[^,]{3,80})$", re.I)

    async def _last_clause(self, request: CommandRequest, decision: RouteDecision) -> RouteDecision:
        """'before i forget, open brave' / 'someone's coming, minimize everything': when the whole sentence is not
        understood, the command after a leading remark is. Only an action found that way is taken."""
        weak = decision.lane in (RouteLane.LANE_2, RouteLane.CLARIFY) and decision.reason_code != ReasonCode.QUESTION_NOT_COMMAND \
            and not (decision.slots or {}).get("deliberate_plan")   # a branch / parallel request planned on purpose
        if not weak or _IN_CLAUSE.get():
            return decision
        m = self._REMARK_THEN_COMMAND.match(clean_for_matching(request.text or "").strip())
        if not m or re.search(r"\b(?:don'?t|do\s+not|never|not)\b", m.group("remark"), re.I) \
                or re.search(r"\b(?:don'?t|do\s+not|never|not|instead\s+of|except|without)\b", m.group("cmd"), re.I):
            return decision
        token = _IN_CLAUSE.set(True)
        try:
            inner = await self._route(CommandRequest(text=m.group("cmd")))
            first = await self._route(CommandRequest(text=m.group("remark")))
        finally:
            _IN_CLAUSE.reset(token)
        if first.lane in (RouteLane.LANE_0, RouteLane.LANE_1, RouteLane.CONTROL) and first.intent \
                and not re.match(r"(?:i|i'm|im|i've|my|we|we're|it|it's|this|that|there)\b", m.group("remark").strip(), re.I) \
                and first.intent not in ("chat", "general_chat", "ollama_chat", "quick_answer", "search_web"):
            return decision   # "close chrome, then lock the pc": the first part is a step too, never dropped
        if inner.lane in (RouteLane.LANE_0, RouteLane.LANE_1) and inner.intent and not inner.subcommands \
                and inner.intent not in self._SEND_INTENTS and not (inner.slots or {}).get("pronoun"):
            return inner
        return decision

    _TELL_PERSON = re.compile(r"^(?:tell|text|message|msg|ping|inform|remind)\s+(?P<who>(?:my\s+)?[a-z][a-z'-]{1,20})\s*,?\s+(?P<msg>.{2,})$", re.I)

    _QUESTION_START = re.compile(r"^(?:(?:hold\s+on|wait|so|and|but|sorry|hey\s+jarvis|jarvis|um+|uh+)\s*,?\s+)*"
                                 r"(?:was|were|did|has|have|is|are|does|do|had)\b(?!\s+(?:not|n't|tell|send|message|text|let|ask|remind|inform|ping|reply)\b)", re.I)

    _NEXT_STEP = re.compile(r"(?:,\s*|\s+)(?:and\s+then|then|and\s+after\s+that|after\s+that|and\s+also)\s+(?:please\s+)?(?:call|ring|dial|open|close|"
                            r"launch|send|set|remind|play|lock|shut|turn|mute|email|text|message|search|find|delete|move|copy|take|start)\b", re.I)

    def _check_recipient(self, decision: RouteDecision, text: str = "") -> RouteDecision:
        if decision.intent not in self._SEND_INTENTS:
            return decision
        if decision.lane == RouteLane.LANE_0 and self._NEXT_STEP.search(str((decision.slots or {}).get("message") or "")):
            # "message amma i reached and then call her": the second step is not part of the message
            return RouteDecision(request_id=decision.request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.6,
                                 source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.COMPLEX, needs_planner=True,
                                 normalized_text=decision.normalized_text, reason_code=ReasonCode.MULTI_STEP)
        if isinstance((decision.slots or {}).get("message"), str) and re.match(r"^[\s,;:.-]+", decision.slots["message"]):
            decision = decision.model_copy(update={"slots": {**decision.slots, "message": decision.slots["message"].lstrip(" ,;:.-")}})
        if decision.lane == RouteLane.LANE_0 and self._QUESTION_START.match((text or "").strip()):
            # "was that message actually sent?" asks about a message; a question never sends one
            return RouteDecision(request_id=decision.request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.6,
                                 source=decision.source, complexity=ComplexityLevel.SIMPLE,
                                 normalized_text=decision.normalized_text, reason_code=ReasonCode.QUESTION_NOT_COMMAND)
        who = str((decision.slots or {}).get("recipient") or (decision.slots or {}).get("to") or "").strip().lower()
        if re.fullmatch(r"\d{1,5}(?:[:.]\d{2})?\s*(?:am|pm)?", who) and decision.intent == "send_whatsapp_message":
            # "tell mom meeting moved to 5": a time or number is never the contact - the person follows "tell"
            m = self._TELL_PERSON.match(clean_for_matching(text).strip())
            if m and m.group("who").lower() not in self._NOT_A_CONTACT:
                from jarvis.core.router.extended import _looks_like_person, _name_like
                if _looks_like_person(m.group("who"), text) or _name_like(m.group("who")):
                    return decision.model_copy(update={"slots": {**decision.slots, "recipient": m.group("who"),
                                                                 "message": m.group("msg").strip()}})
            who = "to"  # unknown: ask who it is for
        msg = str((decision.slots or {}).get("message") or "").strip(" .!?'\"").lower()
        if decision.intent in ("send_whatsapp_message", "send_whatsapp_bulk") and \
                re.fullmatch(r"(?:it|that|this|them|these|those|that one|this one|the same)", msg):
            # "send that to Arun": a pronoun is not the message - say what, or send a file/screenshot by name
            return RouteDecision(request_id=decision.request_id, lane=RouteLane.CLARIFY, intent=decision.intent,
                                 slots={k: v for k, v in decision.slots.items() if k != "message"}, confidence=0.4,
                                 source=decision.source, complexity=ComplexityLevel.SIMPLE,
                                 normalized_text=decision.normalized_text,
                                 clarification=f"What should I send{' to ' + who.title() if who else ''}? Tell me the "
                                               "message, or name the file or screenshot.",
                                 reason_code=ReasonCode.LOW_CONFIDENCE, missing_slots=["message"])
        if who and who.strip(" .'\"") in self._NOT_A_CONTACT:
            return RouteDecision(request_id=decision.request_id, lane=RouteLane.CLARIFY, intent=decision.intent,
                                 slots={k: v for k, v in decision.slots.items() if k not in ("recipient", "to")}, confidence=0.4,
                                 source=decision.source, complexity=ComplexityLevel.SIMPLE,
                                 normalized_text=decision.normalized_text, clarification="Who should I send it to?",
                                 reason_code=ReasonCode.LOW_CONFIDENCE, missing_slots=["recipient"])
        return decision

    def _check_frame_safety(self, decision: RouteDecision, text: str = "") -> RouteDecision:
        if not hasattr(self, "frame_extractor") or not text:
            return decision
        content = str((decision.slots or {}).get("message") or (decision.slots or {}).get("text") or "")
        if content and len(content) >= 3 and content.lower() in text.lower():
            # "tell ganesh to start without me": a "not / without" inside the words to send is the message, not a
            # negation of sending it
            i = text.lower().find(content.lower())
            text = (text[:i] + " " + text[i + len(content):]).strip()
        try:
            frame = self.frame_extractor.extract(text, self.working_memory, self.reference_resolver)
            if frame.negative_targets:
                # 1. Check if decision intent itself matches negative targets
                if decision.intent and frame.is_action_blocked(decision.intent):
                    return RouteDecision(
                        request_id=decision.request_id,
                        lane=RouteLane.REJECT,
                        intent=None,
                        slots={},
                        confidence=1.0,
                        source=decision.source,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=decision.normalized_text,
                        clarification=f"Command was negated. Action '{decision.intent}' was excluded.",
                        reason_code=ReasonCode.NEGATED_ACTION,
                    )
                # 2. Check if an app target was negated (e.g. "open Edge, not Chrome")
                app = str((decision.slots or {}).get("name") or (decision.slots or {}).get("app") or "").strip().lower()
                if app and any(neg.lower() == app or neg.lower() in app for neg in frame.negative_targets):
                    return RouteDecision(
                        request_id=decision.request_id,
                        lane=RouteLane.REJECT,
                        intent=None,
                        slots={},
                        confidence=1.0,
                        source=decision.source,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=decision.normalized_text,
                        clarification=f"Command was negated. Target application '{app}' was excluded.",
                        reason_code=ReasonCode.NEGATED_ACTION,
                    )
        except Exception:
            pass
        return decision

    def _match_computer_agent(self, clean_lower: str, routing_text: str, request_id: str, t0: float, breakdown: dict) -> RouteDecision | None:
        """High-speed deterministic routing for task-scoped computer agent operations."""
        # 1. Project Discovery & Architecture Summarization
        m_proj_disc = re.match(
            r"^(?:please )?(?:open|inspect|summarize|understand|explain|go through)(?: my| the)? ([a-zA-Z0-9_\-\.\s]+?) project(?: and (?:summarize it|explain what it does|tell me what it does))?$"
            r"|^(?:open my|open the) ([a-zA-Z0-9_\-\.\s]+?) project$"
            r"|^(?:go through (?:the whole|this|my) project(?: and (?:explain what it does|summarize it))?|summarize this project|understand the whole project|explain this project|explain how it works)$"
            r"|^(?:look through this repo and tell me how (.+?) works)$",
            clean_lower,
        )
        if m_proj_disc:
            p_name = (m_proj_disc.group(1) or m_proj_disc.group(2) or "").strip()
            p_slots = {"project_name": p_name} if p_name else {}
            p_disc_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="project_discover",
                slots=p_slots,
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, p_disc_dec, self.registry_version)
            self._record(p_disc_dec)
            return p_disc_dec

        # 2. Project Run / Start
        m_proj_run = re.match(
            r"^(?:please )?(?:run|start|launch|bring up) (?:the |my )?project(?: and check database)?$"
            r"|^(?:run|start|launch|bring up)(?: my| the)? ([a-zA-Z0-9_\-\.]+) project$"
            r"|^(?:start|run) (?:the )?(?:backend and frontend|frontend and backend)$"
            r"|^(?:run|bring up|start) (?:my |the )?automate(?: project| thing)?(?: and get it running)?$"
            r"|^(?:run it|run all|run all files|run project files|bring the automate thing up and get it running)$",
            clean_lower,
        )
        if m_proj_run:
            p_name = (m_proj_run.group(1) or ("automate" if "automate" in clean_lower else "")).strip()
            run_slots = {"project_name": p_name} if p_name else {}
            if "backend" in clean_lower and "frontend" in clean_lower:
                run_slots["components"] = ["backend", "frontend"]
            elif "run all" in clean_lower or "all files" in clean_lower:
                run_slots["components"] = ["all"]
            p_run_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="project_run",
                slots=run_slots,
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, p_run_dec, self.registry_version)
            self._record(p_run_dec)
            return p_run_dec

        # 2b. Controlled Chrome & Chrome Extension Launch
        m_chrome_ext = re.match(
            r"^(?:please )?(?:launch controlled chrome|start controlled chrome|use (?:that |the )?chrome extension|run (?:the )?(?:chrome )?extension|open (?:the )?chrome extension|launch chrome with (?:the )?extension)$",
            clean_lower,
        )
        if m_chrome_ext:
            p_ext_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="controlled_chrome_launch",
                slots={"project_name": "automate"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, p_ext_dec, self.registry_version)
            self._record(p_ext_dec)
            return p_ext_dec

        # 2c. Project File Read
        m_proj_read = re.match(
            r"^(?:please )?(?:read|show|inspect|view) (?:the )?(?:project )?file (.+)$"
            r"|^(?:read files of (?:the )?project|read project files)$",
            clean_lower,
        )
        if m_proj_read:
            target_f = (m_proj_read.group(1) or "").strip()
            p_rf_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="project_file_read",
                slots={"file_path": target_f} if target_f else {"file_path": "README.md"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, p_rf_dec, self.registry_version)
            self._record(p_rf_dec)
            return p_rf_dec

        # 3. Project Stop
        if re.match(r"^(?:please )?(?:stop|shutdown|kill) (?:the |my )?project(?: components)?$|^(?:stop|kill) (?:the )?(?:backend and frontend|frontend and backend)$|^stop project components safely$", clean_lower):
            p_stop_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="project_stop",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, p_stop_dec, self.registry_version)
            self._record(p_stop_dec)
            return p_stop_dec

        # 4. Project Logs & Diagnostic
        m_proj_logs = re.match(
            r"^(?:please )?(?:show|view|read|get|check)(?: the)? (?:backend|frontend|project) logs?$"
            r"|^(?:why isn't the backend (?:starting|working)|find why the backend isn't starting|read backend error|read backend logs|show backend logs)$"
            r"|^(?:why is (?:the )?backend failing|why isn't (?:the )?project running|why isn't (?:the )?frontend starting)$",
            clean_lower,
        )
        if m_proj_logs:
            comp = "backend" if "backend" in clean_lower else ("frontend" if "frontend" in clean_lower else "project")
            p_logs_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="project_logs",
                slots={"component": comp},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, p_logs_dec, self.registry_version)
            self._record(p_logs_dec)
            return p_logs_dec

        # 5. Database Status
        if re.match(r"^(?:please )?(?:check whether the database is connected|check database connection|check database|is database connected|is database running|database status)$", clean_lower):
            db_status_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="database_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, db_status_dec, self.registry_version)
            self._record(db_status_dec)
            return db_status_dec

        # 6. Git Diff
        if re.match(r"^(?:please )?(?:show me the diff|show (?:me )?(?:the )?changes|show diff|git diff)$", clean_lower):
            diff_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="git_diff",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, diff_dec, self.registry_version)
            self._record(diff_dec)
            return diff_dec

        # 7. Run Project Tests
        if re.match(r"^(?:please )?(?:run the tests(?: again)?|run tests(?: again)?|run project tests|rerun tests|test project)$", clean_lower):
            test_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="run_project_tests",
                slots={"repo_path": "."},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, test_dec, self.registry_version)
            self._record(test_dec)
            return test_dec

        # 8. Code Repair & Error Fixing Loop
        if re.match(r"^(?:please )?(?:fix the issue|fix the error|fix it|fix this project|fix backend|repair the issue|fix the backend problem and rerun the tests)$", clean_lower):
            repair_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="code_repair_loop",
                slots={"error_summary": "Traceback: check backend error"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, repair_dec, self.registry_version)
            self._record(repair_dec)
            return repair_dec

        # 9. Code Search / Error Source
        m_code_search = re.match(
            r"^(?:please )?(?:locate source file causing error|find the source of the error|find error source|open the error file)$"
            r"|^(?:where is (.+?) (?:handled|defined|located|generated))$",
            clean_lower,
        )
        if m_code_search:
            q_sym = (m_code_search.group(1) or "error").strip()
            code_search_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="code_search",
                slots={"query": q_sym},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, code_search_dec, self.registry_version)
            self._record(code_search_dec)
            return code_search_dec

        # 10. Exam / Assessment Helper
        m_exam = re.match(
            r"^(?:please )?(?:solve|answer|help with|help me with)(?: this| the| a)?(?: [a-zA-Z0-9_\-]+)*? (?:exam|quiz|test|assessment|practice question|mock test)(?: question)?(?:: (.+))?$",
            clean_lower,
        ) or re.match(
            r"^(?:please )?(?:solve|answer|help with) (?:this |the |a )?(?:practice question|mock question|homework question|quiz question|exam question)(?:: (.+))?$",
            clean_lower,
        )
        if m_exam:
            q_text = (m_exam.group(1) or clean_lower).strip()
            is_mock = any(k in clean_lower for k in ("practice", "mock", "study", "homework"))
            exam_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="exam_assessment_helper",
                slots={"question": q_text, "is_practice_or_mock": is_mock},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, exam_dec, self.registry_version)
            self._record(exam_dec)
            return exam_dec

        # 12. Take Screenshot and Send to Phone
        if re.match(r"^(?:please )?(?:take (?:a )?screenshot and send (?:it )?to (?:my )?phone|send (?:a |the )?screenshot to (?:my )?phone)$", clean_lower):
            shot_phone_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="compound_screenshot_phone",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.COMPOUND,
                subcommands=[
                    SubCommand(intent="take_screenshot", tool="take_screenshot", arguments={}),
                    SubCommand(intent="android_push_file", tool="android_push_file", arguments={"path": "latest_screenshot"}),
                ],
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, shot_phone_dec, self.registry_version)
            self._record(shot_phone_dec)
            return shot_phone_dec

        return None

    async def _route(self, request: CommandRequest | str) -> RouteDecision:
        t0 = perf_counter_ns()
        if isinstance(request, str):
            request = CommandRequest(text=request)
        original_text = request.text
        request_id = request.request_id
        breakdown: dict[str, float] = {}

        # 1. CONTROL COMMAND CHECK (< 1 ms)
        t_ctrl_0 = perf_counter_ns()
        control_decision = match_control(original_text, request_id)
        breakdown["control_match_ms"] = (perf_counter_ns() - t_ctrl_0) / 1e6
        if control_decision:
            control_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
            control_decision.breakdown_ms = breakdown
            self._record(control_decision)
            return control_decision

        # 2. NORMALIZATION
        t_norm_0 = perf_counter_ns()
        _, routing_text = normalize_text(original_text)
        breakdown["normalization_ms"] = (perf_counter_ns() - t_norm_0) / 1e6

        if not routing_text:
            orig_lower = original_text.lower().strip().rstrip(".!,?")
            wake_phrases = {"hey jarvis", "jarvis", "hello", "hi", "wake", "wake up", "are you there", "dashboard"}
            if orig_lower in wake_phrases or any(orig_lower.startswith(wp) for wp in wake_phrases):
                decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent="show_dashboard",
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=original_text,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(decision)
                return decision
            if re.search(r"\b(?:thank|thanks|thx|ty|cheers|good\s+job|well\s+done)\b", orig_lower):
                # "um thank you so much jarvis": all of it is conversation, answered by the assistant
                decision = RouteDecision(request_id=request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.95,
                                         source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE, normalized_text=original_text,
                                         reason_code=ReasonCode.QUESTION_NOT_COMMAND, routing_ms=(perf_counter_ns() - t0) / 1e6)
                self._record(decision)
                return decision

            decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent=None,
                confidence=0.0,
                source=RouteSource.EXACT,
                normalized_text="",
                clarification="I didn't hear a command. How can I help you?",
                reason_code=ReasonCode.UNKNOWN_INTENT,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(decision)
            return decision

        clean_text = clean_for_matching(original_text) or original_text  # wake words / fillers / thanks / typos removed

        # 3a-0. Follow-ups about what JARVIS just did ("who did you send that to?") come from the action record,
        # never from a messaging pattern that would treat "you" / "me" as a contact.
        from jarvis.core.action_log import is_followup
        if is_followup(clean_text):
            follow = RouteDecision(
                request_id=request_id, lane=RouteLane.LANE_0, intent="recent_actions", slots={"question": original_text.strip()},
                confidence=1.0, source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE, normalized_text=routing_text,
                reason_code=ReasonCode.EXACT_PATTERN, routing_ms=(perf_counter_ns() - t0) / 1e6, breakdown_ms=breakdown)
            self._record(follow)
            return follow

        # 3a. "Reply to everyone who messaged me ... don't reply in groups": the constraint is part of the
        # request, not a negation of it, so this is decided before the negation guard.
        from jarvis.core.router.extended import match_auto_reply, match_bulk_reply
        # the original wording: cleaning drops a leading "for the next hour," that is the auto-reply window
        bulk_decision = match_auto_reply(original_text, request_id) or match_bulk_reply(clean_text, request_id)
        if bulk_decision:
            bulk_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
            bulk_decision.breakdown_ms = breakdown
            self._record(bulk_decision)
            return bulk_decision

        # 3a-1. META / RESPONSE-POLICY INSTRUCTION CHECK (evaluated before negation check)
        from jarvis.core.router.meta_policy import match_meta_policy
        meta_decision = match_meta_policy(clean_text or routing_text, request_id)
        if meta_decision:
            meta_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
            meta_decision.breakdown_ms = breakdown
            self._record(meta_decision)
            return meta_decision

        # 3a-2. DICTATION CONTEXT GATE (evaluated before negation and capability routing)
        from jarvis.core.desktop.dictation_controller import (
            get_dictation_controller,
            classify_dictation_turn,
            DictationTurnType,
            DictationState,
        )
        dict_ctrl = get_dictation_controller()
        if dict_ctrl.is_active:
            turn = classify_dictation_turn(clean_text or routing_text, dict_ctrl.state)
            if turn:
                if turn.turn_type == DictationTurnType.GLOBAL_EMERGENCY_COMMAND:
                    if turn.escape_command and turn.escape_command != "cancel":
                        dict_ctrl.stop()
                        original_text = turn.escape_command
                        clean_text = turn.escape_command
                        routing_text = turn.escape_command
                    else:
                        dict_ctrl.stop()
                        stop_dec = RouteDecision(
                            request_id=request_id,
                            lane=RouteLane.CONTROL,
                            intent="dictation_mode_control",
                            slots={"action": "stop"},
                            confidence=1.0,
                            source=RouteSource.EXACT,
                            complexity=ComplexityLevel.SIMPLE,
                            normalized_text=routing_text,
                            reason_code=ReasonCode.EXACT_PATTERN,
                            routing_ms=(perf_counter_ns() - t0) / 1e6,
                            breakdown_ms=breakdown,
                        )
                        self._record(stop_dec)
                        return stop_dec
                else:
                    # Captured by active dictation - STRICT CAPABILITY ISOLATION
                    if turn.turn_type == DictationTurnType.DICTATION_CONTROL:
                        intent = "dictation_mode_control"
                        slots = {"action": turn.operation.lower()}
                    elif turn.turn_type == DictationTurnType.EDIT_COMMAND:
                        intent = "voice_edit"
                        slots = {"action": turn.operation.lower(), **turn.slots}
                    elif turn.turn_type == DictationTurnType.MIXED:
                        intent = "voice_edit"
                        slots = {"action": "mixed", "operations": turn.operations}
                    elif turn.turn_type == DictationTurnType.LITERAL_TEXT:
                        intent = "dictate_text"
                        slots = {"text": turn.text, "literal": True}
                    else:
                        intent = "dictate_text"
                        slots = {"text": turn.text}

                    dict_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent=intent,
                        slots=slots,
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=routing_text,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(dict_dec)
                    return dict_dec
        else:
            # Controller is IDLE: check for start typing or literal mode
            turn = classify_dictation_turn(clean_text or routing_text, dict_ctrl.state)
            if turn and turn.turn_type in (DictationTurnType.START_DICTATION, DictationTurnType.LITERAL_TEXT):
                if dict_ctrl.has_editable_target() or turn.slots.get("app"):
                    start_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent="dictate_text",
                        slots={"action": "start", "text": turn.text or "", "target_app": turn.slots.get("app", "")},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=routing_text,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(start_dec)
                    return start_dec
                else:
                    # No editable target: ask ONLY "Where should I type?"
                    # Never route to PowerShell / general tool search
                    clarify_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.CLARIFY,
                        intent="clarify",
                        slots={},
                        confidence=1.0,
                        clarification="Where should I type?",
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=routing_text,
                        reason_code=ReasonCode.LOW_CONFIDENCE,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(clarify_dec)
                    return clarify_dec

        # 3. NEGATION CHECK (prevents execution)
        is_negated, constraints = check_negation(routing_text)
        positive_override = next((c["target"] for c in constraints if c.get("type") == "positive_override"), None)
        if is_negated and not positive_override:
            decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.REJECT,
                intent=None,
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=routing_text,
                clarification="Command was negated. No action taken.",
                reason_code=ReasonCode.NEGATED_ACTION,
                constraints=constraints,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(decision)
            return decision

        if positive_override:
            _, routing_text = normalize_text(positive_override)

        # 3.0 OPERATOR PRIMITIVES (windows, controls, text edits, delivery, tabs, video, IDE, watches): the object
        # acted on picks the capability; the app in front only settles an implicit object ("go back", "next page")
        from jarvis.core.router.operator_intents import match_operator
        op_decision = match_operator(clean_text or routing_text, original_text, request_id, mode=self._operator_mode())
        if op_decision:
            op_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
            op_decision.breakdown_ms = breakdown
            self._record(op_decision)
            return op_decision

        # 3.1 TYPED SEMANTIC FRAME ROUTING (Slots, Temporal, Ordinals, Corrections, Negations)
        frame = self.frame_extractor.extract(original_text, self.working_memory, self.reference_resolver)

        # 3.1a Send Resource with Negated Resource Type ("Send only the PDF, not the screenshot")
        if frame.intent == "send_resource" and "screenshot" in frame.negative_targets:
            target_p = None
            if self.reference_resolver:
                res = self.reference_resolver.resolve_for_slot("pdf", expected_slot_type="file")
                if res and res.confidence == ReferenceConfidence.HIGH and res.referent:
                    target_p = res.referent
            if target_p:
                send_dec = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent="localsend_file",
                    slots={"path": target_p},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    risk="REVERSIBLE",
                    normalized_text=routing_text,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(send_dec)
                return send_dec
            else:
                send_dec = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent="localsend_file",
                    slots={},
                    confidence=0.5,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    clarification="Which PDF would you like to send?",
                    missing_slots=["path"],
                    normalized_text=routing_text,
                    reason_code=ReasonCode.LOW_CONFIDENCE,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(send_dec)
                return send_dec

        # 3.1b Ordinal Applied to Filtered Pool ("Open the third PDF inside Downloads")
        if frame.ordinals and (frame.file_types or frame.folders) and frame.intent in ("open_file", "find_file"):
            if self.reference_resolver:
                res = self.reference_resolver.resolve_for_slot(original_text, expected_slot_type="file")
                if res.confidence == ReferenceConfidence.HIGH and res.referent:
                    open_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent="open_file",
                        slots={"path": res.referent},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        risk="REVERSIBLE",
                        normalized_text=routing_text,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(open_dec)
                    return open_dec
                else:
                    open_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.CLARIFY,
                        intent="open_file",
                        slots={},
                        confidence=0.3,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        clarification=res.clarification_prompt or "No matching file found.",
                        missing_slots=["path"],
                        normalized_text=routing_text,
                        reason_code=ReasonCode.LOW_CONFIDENCE,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(open_dec)
                    return open_dec

        # 3.1c Typed File Search (Temporal ranges, size bounds, exclusions, owner entities)
        # "search youtube for harris jayaraj songs": a named website is where to search, "songs" is not a file type there
        on_web = re.search(r"\b(?:youtube|google|bing|duckduckgo|the\s+web|internet|online|wikipedia|amazon|flipkart|spotify|"
                           r"github|stack\s*overflow|reddit)\b", routing_text or "", re.I)
        if frame.intent == "find_file" and not on_web and (frame.temporal_constraints or frame.size_constraints or frame.exclude_constraints or frame.entities or (frame.file_types and not frame.ordinals)):
            find_slots: dict[str, Any] = {}
            if frame.file_types:
                ft = frame.file_types[0]
                if ft in ("pdf", "docx", "xlsx", "pptx", "txt", "py", "zip", "csv"):
                    find_slots["type_hint"] = f".{ft}"
                elif ft == "image":
                    find_slots["type_hint"] = ".png"
            if frame.folders:
                find_slots["directory_hint"] = frame.folders[0]
            if frame.size_constraints:
                sc = frame.size_constraints[0]
                if sc.min_bytes is not None:
                    find_slots["size_min_bytes"] = sc.min_bytes
                if sc.max_bytes is not None:
                    find_slots["size_max_bytes"] = sc.max_bytes
            if frame.temporal_constraints:
                tc = frame.temporal_constraints[0]
                from datetime import datetime as dt_cls, time as dt_time
                from jarvis.core.capabilities.temporal import DatePoint, DateRange, DateTimePoint, DateTimeRange, TimeRange
                if isinstance(tc, DatePoint):
                    find_slots["time_start_iso"] = dt_cls.combine(tc.resolved_date, dt_time.min).isoformat()
                    find_slots["time_end_iso"] = dt_cls.combine(tc.resolved_date, dt_time.max).isoformat()
                elif isinstance(tc, DateRange):
                    find_slots["time_start_iso"] = dt_cls.combine(tc.start_date, dt_time.min).isoformat()
                    find_slots["time_end_iso"] = dt_cls.combine(tc.end_date, dt_time.max).isoformat()
                elif isinstance(tc, DateTimePoint):
                    find_slots["time_start_iso"] = tc.resolved_dt.isoformat()
                elif isinstance(tc, DateTimeRange):
                    find_slots["time_start_iso"] = tc.start_dt.isoformat()
                    find_slots["time_end_iso"] = tc.end_dt.isoformat()
                elif isinstance(tc, TimeRange):
                    find_slots["time_start_iso"] = tc.start_time.isoformat()
                    find_slots["time_end_iso"] = tc.end_time.isoformat()
                find_slots["time_hint"] = tc.label
            if frame.exclude_constraints:
                find_slots["exclude_patterns"] = frame.exclude_constraints

            # Set query text cleanly
            if frame.entities and frame.include_constraints:
                find_slots["query"] = " ".join(frame.entities + frame.include_constraints)
            elif frame.include_constraints:
                find_slots["query"] = " ".join(frame.include_constraints)
            elif frame.entities:
                find_slots["query"] = " ".join(frame.entities)
            elif frame.file_types and not (frame.folders or frame.temporal_constraints or frame.size_constraints) \
                    and self._file_subject(frame.clean_query or routing_text):
                # "find my resume pdf": "resume" is what to look for, "pdf" only narrows the type
                find_slots["query"] = self._file_subject(frame.clean_query or routing_text)
            elif re.search(r"\b[a-z0-9][\w-]*\.[a-z][a-z0-9]{1,4}\b", routing_text.lower()) and frame.file_types:
                # "find report.pdf": the file name is the query, its extension only the type
                find_slots["query"] = re.search(r"\b[a-z0-9][\w-]*\.[a-z][a-z0-9]{1,4}\b", routing_text.lower()).group(0)
            elif frame.file_types or frame.folders or frame.temporal_constraints or frame.size_constraints:
                # Pure constraint search without target filename (e.g. "Find PDFs from last Tuesday", "Show files bigger than 20MB")
                find_slots["query"] = "*"
            else:
                find_slots["query"] = frame.clean_query or "*"

            find_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="find_file",
                slots=find_slots,
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                risk="READ_ONLY",
                normalized_text=routing_text,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(find_dec)
            return find_dec

        # 3.1d Numeric Correction on Volume/Brightness ("Set the volume to thirty-five percent, not fifty")
        if frame.corrections and any(c.get("type") == "numeric_override" for c in frame.corrections) and any(w in routing_text.lower() for w in ("volume", "sound", "brightness")):
            from jarvis.core.capabilities.frame import parse_spoken_number
            num_corr = next(c for c in frame.corrections if c.get("type") == "numeric_override")
            val_pct = parse_spoken_number(num_corr["new_value"])
            if val_pct is None:
                try:
                    val_pct = int(num_corr["new_value"])
                except Exception:
                    val_pct = frame.numeric_constraints[0].value if frame.numeric_constraints else 50
            intent_name = "brightness_set" if "brightness" in routing_text.lower() else "volume_set"
            vol_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent=intent_name,
                slots={"percentage": val_pct, "percent": val_pct},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                risk="REVERSIBLE",
                normalized_text=routing_text,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(vol_dec)
            return vol_dec

        # 3.1e Search Notes ("search my notes for password hints")
        if frame.intent == "search_notes" and not re.search(r"\bnotes?\.[a-z0-9]{1,5}\b", routing_text, re.I):   # notes.txt is a file
            m_nq = re.search(r"\bnotes?\s+(?:for|about|on|regarding)\s+(?P<q>.+)$", routing_text, re.I) or \
                   re.search(r"\bsearch\s+(?:my\s+)?notes?\s+(?:for\s+)?(?P<q>.+)$", routing_text, re.I)
            q_val = m_nq.group("q").strip() if m_nq else (frame.clean_query or "")
            q_val = re.sub(r"^(?:for|about|on)\s+", "", q_val).strip()
            notes_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="search_notes",
                slots={"query": q_val},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                risk="READ_ONLY",
                normalized_text=routing_text,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(notes_dec)
            return notes_dec

        # 3b. DIRECT SYSTEM ACTIONS & DASHBOARD BUTTONS (< 0.5 ms)
        clean_lower = routing_text.strip().lower()

        # Unsupported physical / external / non-desktop domain check
        from jarvis.core.router.unsupported import check_unsupported_external
        unsupported_dec = check_unsupported_external(clean_lower, request_id)
        if unsupported_dec:
            unsupported_dec.routing_ms = (perf_counter_ns() - t0) / 1e6
            unsupported_dec.breakdown_ms = breakdown
            self._record(unsupported_dec)
            return unsupported_dec

        if re.search(r"\b(?:diagnostics?|run diagnostics?|diagnostic check|system diagnostics?|system audit|subsystem audit|subsystem diagnostic check)\b", clean_lower):
            diag_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="system_diagnostics",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, diag_decision, self.registry_version)
            self._record(diag_decision)
            return diag_decision

        # 3a. CONVERSATIONAL CONTINUITY & FOLLOW-UP CHECK (< 0.5 ms)
        working_ctx = getattr(self.working_memory, "context", None) if self.working_memory else None
        followup = FollowupDetector.classify(routing_text, working_ctx)

        # 3a-1. ACTIVE PENDING CONFIRMATION / CANCELLATION (Section 43 & 44)
        if followup.followup_type == FollowupType.CONFIRMATION and \
                len(re.findall(r"[a-z0-9']+", original_text.lower())) <= len(routing_text.split()) + 3:
            pending_conf = getattr(self.working_memory, "get_pending_confirmation", lambda: None)()
            if pending_conf:
                self.working_memory.set_pending_confirmation(None)
                conf_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CONTROL,
                    intent="confirm_ticket",
                    slots={"ticket_id": pending_conf.ticket_id},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(conf_decision)
                return conf_decision

        elif followup.followup_type == FollowupType.CANCELLATION:
            pending_conf = getattr(self.working_memory, "get_pending_confirmation", lambda: None)()
            if pending_conf:
                self.working_memory.set_pending_confirmation(None)
                canc_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CONTROL,
                    intent="reject_ticket",
                    slots={"ticket_id": pending_conf.ticket_id},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(canc_decision)
                return canc_decision

        # 3a-2. WHY QUERY / ERROR EXPLANATION (Section 46)
        elif followup.followup_type == FollowupType.WHY_QUERY:
            last_fail = getattr(self.working_memory, "get_last_failure", lambda: None)()
            if last_fail:
                target = last_fail.get("target", "The target")
                reason = last_fail.get("reason", "unknown error")
                if reason in ("APP_NOT_FOUND", "not_found"):
                    msg = f"{target} wasn't present in the current application catalog."
                else:
                    msg = f"{target} failed: {reason}."
                why_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent="system_info",
                    slots={"message": msg},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    clarification=msg,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(why_decision)
                return why_decision

        # 3a-3. TOPIC SWITCH (Section 20)
        elif followup.followup_type == FollowupType.TOPIC_SWITCH and followup.target_hint:
            if self.working_memory:
                restored = getattr(self.working_memory, "restore_topic", lambda x: None)(followup.target_hint)
                if not restored and hasattr(self.working_memory, "push_topic"):
                    from jarvis.core.context.models import TopicRef, EntityType
                    self.working_memory.push_topic(TopicRef(
                        entity_id=f"topic_{followup.target_hint.lower().replace(' ', '_')}",
                        canonical_name=followup.target_hint.lower(),
                        display_name=followup.target_hint.title(),
                        entity_type=EntityType.TOPIC,
                    ))

        # 3a-4. ACTION ON TOPIC / PRONOUN CONTINUITY (Sections 13-16, 24, 36)
        if clean_lower in ("open its folder", "show its folder", "open parent folder"):
            if self.reference_resolver:
                res = self.reference_resolver.resolve("same folder")
                if res.referent and res.confidence == ReferenceConfidence.HIGH:
                    exp_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent="open_app",
                        slots={"name": "explorer", "path": str(res.referent), "referent": "parent_dir"},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(exp_decision)
                    return exp_decision

        elif clean_lower in ("where is it", "where is it stored", "where is it located", "where did it install"):
            if self.reference_resolver:
                res = self.reference_resolver.resolve(clean_lower)
                if res.referent and res.confidence == ReferenceConfidence.HIGH:
                    loc_intent = "file.location" if res.referent_type == "FILE" else "get_app_location"
                    loc_slot = "path" if res.referent_type == "FILE" else "name"
                    loc_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent=loc_intent,
                        slots={loc_slot: str(res.referent)},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(loc_decision)
                    return loc_decision

        elif "send" in clean_lower and any(d in clean_lower for d in ("phone", "mobile", "android")) and any(p in clean_lower for p in ("it", "this", "that")):
            if self.reference_resolver:
                res = self.reference_resolver.resolve_for_slot(clean_lower, expected_slot_type="file")
                if res.referent and res.confidence == ReferenceConfidence.HIGH:
                    phone_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent="phone.send_file",
                        slots={"path": str(res.referent), "destination": "phone"},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(phone_decision)
                    return phone_decision

        elif clean_lower in ("open it", "launch it", "run it"):
            if self.reference_resolver:
                res = self.reference_resolver.resolve(clean_lower)
                if res.referent and res.confidence == ReferenceConfidence.HIGH:
                    open_intent = "open_file" if res.referent_type == "FILE" else "open_app"
                    open_slot = "path" if res.referent_type == "FILE" else "name"
                    open_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent=open_intent,
                        slots={open_slot: str(res.referent)},
                        confidence=1.0,
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(open_decision)
                    return open_decision

        # 3b. CLARIFICATION CANDIDATE ORDINAL SELECTION / RESULT SET ORDINAL
        m_ord = re.match(r"^(?:the\s+)?(?:(1st|first|1|one|1\s*st)(?:\s+(?:1|one|option))?|(2nd|second|2|two|2\s*nd)(?:\s+(?:2|two|option|one))?|(3rd|third|3|three|3\s*rd)(?:\s+(?:3|three|option|one))?|(4th|fourth|4|four|4\s*th)(?:\s+(?:4|four|option|one))?)$", clean_lower, re.I)
        if self.last_clarification_candidates and m_ord:
            idx = 0 if m_ord.group(1) else (1 if m_ord.group(2) else (2 if m_ord.group(3) else 3))
            if idx < len(self.last_clarification_candidates):
                selected = self.last_clarification_candidates[idx]
                self.last_clarification_candidates = []
                intent_target = self.last_clarification_intent if self.last_clarification_intent != "clarify" else "open_app"
                slot_key = "path" if "file" in intent_target else "name"
                ord_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent=intent_target,
                    slots={slot_key: selected},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ord_decision)
                return ord_decision

        elif (m_ord or followup.followup_type == FollowupType.ORDINAL_REFERENCE) and self.reference_resolver:
            res = self.reference_resolver.resolve(clean_lower)
            if res.referent and res.confidence == ReferenceConfidence.HIGH:
                intent_target = "open_file" if res.referent_type in ("FILE", "SEARCH_RESULT") else "open_app"
                slot_key = "path" if intent_target == "open_file" else "name"
                ord_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent=intent_target,
                    slots={slot_key: str(res.referent)},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ord_decision)
                return ord_decision

        # 3b-verb. A bare verb ("open", "launch the") is half a command - ask for the rest, never guess an app.
        if re.fullmatch(r"(?:open|launch|start|run|close)(?:\s+(?:the|a|an|up))?", clean_lower):
            verb = clean_lower.split()[0]
            bare = RouteDecision(
                request_id=request_id, lane=RouteLane.CLARIFY, intent="clarify", slots={}, confidence=0.3,
                source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE, normalized_text=clean_lower,
                clarification=f"What should I {verb}?", reason_code=ReasonCode.LOW_CONFIDENCE,
                routing_ms=(perf_counter_ns() - t0) / 1e6, breakdown_ms=breakdown)
            self._record(bare)
            return bare

        # 3b-ord. "open the second one" with nothing listed yet: ask, never open an app called "second 1"
        m_ref = re.match(r"^(?:open|pick|take|choose|select|play|show|use)\s+(?:the\s+)?(first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)"
                         r"(?:\s+(?:one|1|file|result|item|document|option|link|video|song|match))?$", clean_lower)
        if m_ref:
            ordinal = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
                       "fifth": 5, "5th": 5, "last": -1}[m_ref.group(1)]
            ref_decision = RouteDecision(
                request_id=request_id, lane=RouteLane.CLARIFY, intent="open_file", slots={"ordinal": ordinal},
                confidence=0.5, source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE, normalized_text=clean_lower,
                clarification="Which list do you mean? Search or list something first, then say 'open the second one'.",
                reason_code=ReasonCode.EXACT_PATTERN, routing_ms=(perf_counter_ns() - t0) / 1e6, breakdown_ms=breakdown)
            self._record(ref_decision)
            return ref_decision

        # 3b-ambig. AMBIGUITY & EXPLICIT CLARIFICATION DIRECTIVE CHECK
        from jarvis.core.router.disambiguation import disambiguate_generic_request
        generic_ambig = disambiguate_generic_request(routing_text or clean_text, self.working_memory, request_id)
        if generic_ambig:
            generic_ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
            generic_ambig.breakdown_ms = breakdown
            self._record(generic_ambig)
            return generic_ambig

        # 3b-comp. COMPUTER AGENT: PROJECT, CODE, DATABASE, DEV ROUTING (< 0.1 ms)
        comp_decision = self._match_computer_agent(clean_lower, routing_text, request_id, t0, breakdown)
        if comp_decision:
            return comp_decision

        # 3b-multi. "open notepad and type hello", "play X on youtube then set volume to 30": split into steps and route
        # each one, so a single-intent matcher never swallows the rest of the sentence as its argument.
        if not _IN_CLAUSE.get():
            multi = await self._route_multi_step(original_text, request_id) or await self._route_multi_step(routing_text or clean_text, request_id)
            if multi:
                multi.routing_ms = (perf_counter_ns() - t0) / 1e6
                multi.breakdown_ms = breakdown
                self._record(multi)
                return multi

        # 3b-ext. EXTENDED DOMAINS: phone control, messaging, knowledge, web, reminders (< 1 ms)
        from jarvis.core.router.extended import match_extended
        if routing_text in ("open notepad", "open calculator", "open chrome"):
            ext_decision = None
        else:
            ext_decision = match_extended(clean_text, request_id) or match_extended(routing_text, request_id)
        if ext_decision:
            ext_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
            ext_decision.breakdown_ms = breakdown
            self._record(ext_decision)
            return ext_decision

        # 3c. DIRECT SHELL / TERMINAL COMMAND CHECK (< 0.5 ms)
        orig_stripped = original_text.strip()
        cmd_match = re.match(r"^(?:cmd:|cmd\s+|powershell:|powershell\s+|ps:|ps\s+|run:|exec:|exec\s+|sh:\s*)(.+)$", orig_stripped, re.IGNORECASE)
        shell_cmd = None
        if cmd_match:
            shell_cmd = cmd_match.group(1).strip()
        elif routing_text:
            first_tok = routing_text.split()[0].lower()
            if first_tok in KNOWN_SHELL_COMMANDS and _looks_like_shell(orig_stripped):
                shell_cmd = orig_stripped

        if shell_cmd:
            cmd_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="powershell_command",
                slots={"command": shell_cmd},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=shell_cmd,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, cmd_decision, self.registry_version)
            self._record(cmd_decision)
            return cmd_decision

        if re.match(r"^(?:re-pair whatsapp|repair whatsapp|pair whatsapp|whatsapp pairing code)$", clean_lower):
            wa_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="whatsapp_action",
                slots={"action": "pair"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wa_decision, self.registry_version)
            self._record(wa_decision)
            return wa_decision

        if re.match(r"^(?:connect whatsapp|reconnect whatsapp)$", clean_lower):
            wa_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="whatsapp_action",
                slots={"action": "connect"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wa_decision, self.registry_version)
            self._record(wa_decision)
            return wa_decision

        if re.match(r"^(?:disconnect whatsapp)$", clean_lower):
            wa_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="whatsapp_action",
                slots={"action": "disconnect"},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wa_decision, self.registry_version)
            self._record(wa_decision)
            return wa_decision

        if re.match(r"^(?:cancel|cancel task|stop task|(?:just\s+)?(?:leave\s+it(?:\s+alone)?|forget\s+(?:it|about\s+it|that)|drop\s+it|skip\s+it|let\s+it\s+go|don'?t\s+bother|no\s+need))$", clean_lower):
            cancel_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.CONTROL,
                intent="cancel_task",
                slots={"action": "cancel"},
                confidence=1.0,
                source=RouteSource.CONTROL,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.CONTROL_COMMAND,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, cancel_decision, self.registry_version)
            self._record(cancel_decision)
            return cancel_decision

        if re.match(r"^(?:stop speaking|stop talking|stop speech|stop voice|stop audio|be quiet|silence|shut up)$", clean_lower):
            stop_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.CONTROL,
                intent="stop_speaking",
                slots={},
                confidence=1.0,
                source=RouteSource.CONTROL,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.CONTROL_COMMAND,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, stop_decision, self.registry_version)
            self._record(stop_decision)
            return stop_decision

        if re.match(r"^(?:restore|restore window|unmaximize|unminimize)$", clean_lower):
            restore_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="restore_window",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, restore_dec, self.registry_version)
            self._record(restore_dec)
            return restore_dec

        # Volume Mute / Silence
        if re.search(r"\b(?:silence|mute)\b", clean_lower) and not re.search(r"\b(?:unmute|un[- ]?silence)\b", clean_lower) and any(w in clean_lower for w in ("sound", "audio", "volume", "speakers", "speaker", "completely", "please", "mute")):
            mute_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="volume_mute",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, mute_dec, self.registry_version)
            self._record(mute_dec)
            return mute_dec

        # Volume Unmute / Restore audio
        if re.search(r"\b(?:unmute|un[- ]?silence)\b", clean_lower) or (any(w in clean_lower for w in ("sound", "audio", "speakers", "speaker", "playback")) and "back on" in clean_lower):
            unmute_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="volume_unmute",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, unmute_dec, self.registry_version)
            self._record(unmute_dec)
            return unmute_dec

        # Window management: Close window / Dismiss window / Send to taskbar
        if re.search(r"\b(?:close|dismiss|shut)\s+(?:the\s+)?(?:open\s+)?(?:top\s+|active\s+|current\s+)?window\b", clean_lower):
            win_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="close_window",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, win_dec, self.registry_version)
            self._record(win_dec)
            return win_dec

        if re.search(r"\b(?:send|minimize)(?:\s+(?:the\s+)?active\s+(?:app|window))?\s+to\s+(?:the\s+)?taskbar\b", clean_lower):
            min_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="minimize_window",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, min_dec, self.registry_version)
            self._record(min_dec)
            return min_dec

        # Window management: Maximize window / Fullscreen
        if re.match(
            r"^(?:please\s+)?(?:maximize(?:\s+(?:the\s+)?(?:active\s+|current\s+|this\s+)?window)?|max(?:\s+window)?|ful+[\s-]*screen(?:\s+(?:this\s+|the\s+)?(?:active\s+|current\s+)?window)?|(?:make\s+(?:it\s+|this\s+|the\s+window\s+)?|go\s+|enter\s+|toggle\s+)?ful+[\s-]*screen)$",
            clean_lower,
        ) and not any(w in clean_lower for w in ("grab", "shot", "capture", "take", "save", "record", "snip")):
            max_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="maximize_window",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, max_dec, self.registry_version)
            self._record(max_dec)
            return max_dec

        # Phone screen mirror
        if re.search(r"\b(?:mirror|screen\s+mirror)(?:\s+my)?(?:\s+android)?(?:\s+phone)?\b|\bphone\s+(?:screen\s+)?mirror\b", clean_lower):
            mirror_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="android_open_control",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, mirror_dec, self.registry_version)
            self._record(mirror_dec)
            return mirror_dec

        # WhatsApp Status Check
        if re.search(r"\bwhatsapp\b.+(?:connected|bridge|connector|live|status)\b", clean_lower):
            wa_status_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="whatsapp_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wa_status_dec, self.registry_version)
            self._record(wa_status_dec)
            return wa_status_dec

        # Battery / WiFi / Time
        if re.search(r"\bbattery(?:\s+percentage|\s+health|\s+level|\s+status)?\b", clean_lower):
            if any(p in clean_lower for p in ("phone", "android", "mobile", "cell")):
                bat_intent = "android_status"
            else:
                bat_intent = "battery_status"
            bat_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent=bat_intent,
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, bat_dec, self.registry_version)
            self._record(bat_dec)
            return bat_dec

        if re.search(r"\b(?:wi-?fi|network\s+connection|wi-?fi\s+connection)\b(?!\s+(?:password|passcode|pin|key|name|code))", clean_lower) \
                and not re.search(r"\b(?:password|passcode)\b", clean_lower):
            wifi_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="wifi_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wifi_dec, self.registry_version)
            self._record(wifi_dec)
            return wifi_dec

        if re.search(r"\b(?:system\s+clock|what\s+time\s+is\s+it|current\s+time|get\s+time)\b", clean_lower):
            time_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="get_time",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, time_dec, self.registry_version)
            self._record(time_dec)
            return time_dec


        if re.match(r"^(?:show |check |get )?(?:microphone|mic) status$|^(?:is |check )?(?:the )?mic(?:rophone)? working$|^(?:test |check )?(?:the )?mic(?:rophone)?$", clean_lower):
            mic_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="microphone_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, mic_decision, self.registry_version)
            self._record(mic_decision)
            return mic_decision

        if re.match(r"^(?:show |check |get )?(?:speech recognition|speech to text|stt|whisper) status$|^(?:is |check )?(?:the )?speech recognition (?:working|active|ready)$", clean_lower):
            stt_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="speech_recognition_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, stt_decision, self.registry_version)
            self._record(stt_decision)
            return stt_decision

        if re.match(r"^(?:show |check |get )?(?:wake word|wakeword|openwakeword) status$|^(?:is |check )?(?:the )?wake word (?:active|working|listening|ready)$", clean_lower):
            wake_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="wake_word_status",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, wake_decision, self.registry_version)
            self._record(wake_decision)
            return wake_decision

        if re.match(r"^(?:show |check |get |list )?(?:connected |audio |hardware )?devices$|^(?:show |list )?(?:connected )?hardware$", clean_lower):
            dev_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="connected_devices",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, dev_decision, self.registry_version)
            self._record(dev_decision)
            return dev_decision

        # Screen capture / Screenshot Fast Path
        if re.match(r"^(?:please )?(?:take (?:a )?screenshot|capture (?:my |the )?screen(?: right now)?|screenshot(?: right now)?|screen grab|screen capture)$", clean_lower):
            shot_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="take_screenshot",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, shot_decision, self.registry_version)
            self._record(shot_decision)
            return shot_decision

        # Brightness Fast Paths
        m_bright = re.match(
            r"^(?:turn |set )?(?:the )?(?:screen |display )?brightness (?:level )?(?:down to |up to |to |at )?(?P<pct>\d+)(?:%| percent)?$"
            r"|^dim (?:the )?(?:screen |display )?(?:brightness )?(?:to |down to )?(?P<pct2>\d+)(?:%| percent)?$",
            clean_lower,
        )
        if m_bright:
            val = int(m_bright.group("pct") or m_bright.group("pct2"))
            bright_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="brightness_set",
                slots={"percent": val},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, bright_dec, self.registry_version)
            self._record(bright_dec)
            return bright_dec

        if re.match(r"^(?:what is |check |show |get )?(?:the )?(?:screen |display )?brightness(?: level)?$|^brightness$", clean_lower):
            bright_get_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="brightness_get",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, bright_get_dec, self.registry_version)
            self._record(bright_get_dec)
            return bright_get_dec

        # Top Memory Consuming Processes
        if re.match(r"^(?:please )?(?:which (?:programs?|apps?|applications?|processes?) (?:are using|use|consume|take) the most (?:memory|ram)|what (?:programs?|apps?|processes?) (?:are using|use) the most (?:memory|ram)|what is using the most (?:memory|ram)|top (?:memory|ram) (?:processes|programs|apps|applications)|memory hogs)$", clean_lower):
            top_mem_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="top_memory_processes",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, top_mem_dec, self.registry_version)
            self._record(top_mem_dec)
            return top_mem_dec

        if re.match(r"^(?:please )?(?:memory status|working memory|check (?:the )?(?:memory|ram)|(?:how much )?(?:memory|ram)(?: is)? (?:currently )?(?:available|free|used)(?: on this pc)?)$", clean_lower):
            mem_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="system_info",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, mem_decision, self.registry_version)
            self._record(mem_decision)
            return mem_decision

        m_see_folder = re.match(r"^(?:can i |could i |let me )?(?:see|view|check|look at)(?: my| the)? (downloads|desktop|documents|pictures|videos)(?: folder)?$|^(?:show )(?:my |the )?(downloads|documents|pictures|videos)(?: folder)?$|^(?:show )(?:my |the )?desktop folder$", clean_lower)
        if m_see_folder:
            f_name = (m_see_folder.group(1) or m_see_folder.group(2) or "desktop").lower()
            from jarvis.core.router.slots import FOLDER_ALIASES
            resolved_path = FOLDER_ALIASES.get(f_name, f"~/{f_name.capitalize()}")
            from pathlib import Path
            actual_path = str(Path(resolved_path).expanduser().resolve())
            see_dec = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="list_directory",
                slots={"path": actual_path, "limit": 100},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, see_dec, self.registry_version)
            self._record(see_dec)
            return see_dec

        # Application Discovery & Management Fast Paths
        if re.match(r"^(?:please )?(?:refresh|rescan|reload|update) (?:my )?(?:installed )?(?:applications|apps|software)$|^(?:refresh|rescan|reload) (?:apps|applications)$", clean_lower):
            ref_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="refresh_applications",
                slots={"force": True},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, ref_decision, self.registry_version)
            self._record(ref_decision)
            return ref_decision

        if re.match(r"^(?:please )?(?:show|list|display|get) (?:all |my )?(?:installed )?(?:applications|apps|programs|software)$|^what (?:applications|apps|software|programs) (?:are|do i have) installed$|^(?:show |list )?(?:installed )?(?:applications|apps)$", clean_lower):
            list_app_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="list_installed_applications",
                slots={},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, list_app_decision, self.registry_version)
            self._record(list_app_decision)
            return list_app_decision

        m_is_inst = re.match(r"^(?:is|check if) (.+?) (?:is )?installed(?: on (?:my|this) (?:pc|computer|machine))?$|^do i have (.+?) installed(?: on (?:my|this) (?:pc|computer|machine))?$|^(?:is|check if)\s+installed(?: on (?:my|this) (?:pc|computer|machine))?$", clean_lower)
        if m_is_inst:
            target_app = (m_is_inst.group(1) or m_is_inst.group(2) or "").strip()
            if not target_app or target_app in ("it", "that", "this", "installed") or target_app.startswith("installed"):
                clarify_dec = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent="check_app_installed",
                    slots={},
                    confidence=0.4,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    clarification="Which application do you want to check?",
                    missing_slots=["name"],
                    normalized_text=clean_lower,
                    reason_code=ReasonCode.LOW_CONFIDENCE,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(clarify_dec)
                return clarify_dec

            check_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="check_app_installed",
                slots={"name": target_app},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, check_decision, self.registry_version)
            self._record(check_decision)
            return check_decision

        m_where_inst = re.match(
            r"^where (?:is|did|was) (.+?) (?:get )?installed(?: at)?$"
            r"|^(?:what is the |show me the |get )?(?:path|location|directory) (?:for|of) (.+?)$"
            r"|^where is the (.+?) executable(?: located)?$"
            r"|^give me the (?:file system )?location of (.+?)$"
            r"|^where on disk (?:can i find|is) (.+?)$",
            clean_lower,
        )
        if m_where_inst:
            target_app = (
                m_where_inst.group(1)
                or m_where_inst.group(2)
                or m_where_inst.group(3)
                or m_where_inst.group(4)
                or m_where_inst.group(5)
            ).strip()
            loc_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="get_app_location",
                slots={"name": target_app},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, loc_decision, self.registry_version)
            self._record(loc_decision)
            return loc_decision

        # (Computer agent matchers handled early at 3b-comp)

        m_install = re.match(r"^(?:please )?(?:install|setup|download and install) ([a-zA-Z0-9_\-\.\s]+?)(?: using winget| via winget)?$", clean_lower)
        if m_install:
            app_to_install = m_install.group(1).strip()
            # If app_to_install is pronoun or reference, resolve through reference resolver
            if app_to_install in ("it", "that", "this", "that one", "this one", "them", "the app", "the software", "the first one", "the second one") and self.reference_resolver:
                res = self.reference_resolver.resolve_for_slot(clean_lower, expected_slot_type="package", intent="app.install_software")
                if res.confidence == ReferenceConfidence.AMBIGUOUS:
                    ambig_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.CLARIFY,
                        intent="clarify",
                        slots={},
                        confidence=0.5,
                        clarification=res.clarification_prompt or "Which application do you want me to install?",
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=clean_lower,
                        reason_code=ReasonCode.AMBIGUOUS_TOP_TWO,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self._record(ambig_dec)
                    return ambig_dec
                elif res.referent and res.confidence == ReferenceConfidence.HIGH:
                    app_to_install = str(res.referent)

            install_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="install_software",
                slots={"name": app_to_install},
                confidence=1.0,
                source=RouteSource.EXACT,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=clean_lower,
                reason_code=ReasonCode.EXACT_PATTERN,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self.cache.put(routing_text, install_decision, self.registry_version)
            self._record(install_decision)
            return install_decision

        # 4. QUESTION / INFORMATIONAL GUARD
        if is_informational_or_question(clean_text, routing_text):
            # Extract entities from question and track active topic (Sections 5, 6, 14, 16)
            ents = EntityExtractor.extract_from_utterance(original_text)
            if ents and self.working_memory:
                for ent in ents:
                    self.working_memory.record_entity(ent)
                if len(ents) == 1:
                    self.working_memory.push_topic(ents[0])
                else:
                    if hasattr(self.working_memory, "clear_active_topic"):
                        self.working_memory.clear_active_topic()
                    elif hasattr(self.working_memory, "context"):
                        self.working_memory.context.active_topic = None

            # Check if this is an informational query on an active document ("What is it about?", "Summarize it")
            if any(q in clean_lower for q in ("what's it about", "what is it about", "what does it talk about", "summarize it")):
                if self.reference_resolver:
                    res = self.reference_resolver.resolve("what is it about")
                    if res.referent and res.confidence == ReferenceConfidence.HIGH:
                        doc_qa_dec = RouteDecision(
                            request_id=request_id,
                            lane=RouteLane.LANE_0,
                            intent="document_qa",
                            slots={"path": str(res.referent), "query": original_text},
                            confidence=1.0,
                            source=RouteSource.EXACT,
                            complexity=ComplexityLevel.SIMPLE,
                            normalized_text=clean_lower,
                            reason_code=ReasonCode.EXACT_PATTERN,
                            routing_ms=(perf_counter_ns() - t0) / 1e6,
                            breakdown_ms=breakdown,
                        )
                        self._record(doc_qa_dec)
                        return doc_qa_dec

            decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_2,
                intent=None,
                confidence=0.9,
                source=RouteSource.COMPLEXITY_GATE,
                complexity=ComplexityLevel.SIMPLE,
                needs_planner=False,
                normalized_text=routing_text,
                clarification="This request asks for information. Routing to knowledge.",
                reason_code=ReasonCode.QUESTION_NOT_COMMAND,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
            )
            self._record(decision)
            return decision

        # 5. HOT ROUTE CACHE LOOKUP (< 0.5 ms)
        t_cache_0 = perf_counter_ns()
        cached = self.cache.get(routing_text, self.registry_version, request_id)
        breakdown["cache_lookup_ms"] = (perf_counter_ns() - t_cache_0) / 1e6
        if cached:
            cached.routing_ms = (perf_counter_ns() - t0) / 1e6
            cached.breakdown_ms = breakdown
            self._record(cached)
            return cached

        # 6. CANDIDATE INTENT RETRIEVAL
        t_cand_0 = perf_counter_ns()
        tokens = routing_text.split()
        candidate_names = self.catalog.retrieve_candidate_intents(tokens, max_candidates=16)
        breakdown["candidate_generation_ms"] = (perf_counter_ns() - t_cand_0) / 1e6

        # 6a. AMBIGUITY & GENERIC ENTITY CHECK
        from jarvis.core.router.disambiguation import disambiguate_generic_request
        generic_ambig = disambiguate_generic_request(routing_text, self.working_memory, request_id)
        if generic_ambig:
            generic_ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
            generic_ambig.breakdown_ms = breakdown
            self._record(generic_ambig)
            return generic_ambig

        # 6b. COMPLEXITY GATE (Phase 4 / Lane 2 Escalation)
        t_gate_0 = perf_counter_ns()
        gate_dec = check_complexity_gate(routing_text, request_id)
        breakdown["complexity_gate_ms"] = (perf_counter_ns() - t_gate_0) / 1e6
        if gate_dec:
            gate_dec.routing_ms = (perf_counter_ns() - t0) / 1e6
            gate_dec.breakdown_ms = breakdown
            self._record(gate_dec)
            return gate_dec

        # 7. DETERMINISTIC COMPOUND COMMAND CHECK (e.g. "open chrome and calculator" or multi-action clauses)
        if any(sep in routing_text for sep in (" and ", " & ", ",", ";", " then ")):

            compound = check_deterministic_compound(routing_text, self.catalog, request_id)
            if compound:
                compound.routing_ms = (perf_counter_ns() - t0) / 1e6
                compound.breakdown_ms = breakdown
                self.cache.put(routing_text, compound, self.registry_version)
                self._record(compound)
                return compound

        # 7b. CONTEXTUAL PRONOUN & REFERENT RESOLUTION (< 0.2 ms)
        if self.reference_resolver and any(p in routing_text for p in ("open it", "open that", "close it", "close that", "run it")):
            res = self.reference_resolver.resolve(routing_text)
            if res and res.confidence.value in ("HIGH", "high") and res.referent:
                intent_target = "open_file" if res.referent_type == "FILE" else "open_app"
                slot_key = "path" if res.referent_type == "FILE" else "name"
                if "close" in routing_text:
                    intent_target = "close_app"
                    slot_key = "name"
                ref_dec = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent=intent_target,
                    slots={slot_key: str(res.referent)},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=routing_text,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ref_dec)
                return ref_dec

        # 8. EXACT & GRAMMAR PATTERN MATCH
        t_pat_0 = perf_counter_ns()
        pattern_match = match_patterns(routing_text, candidate_names, self.catalog, request_id)
        breakdown["pattern_match_ms"] = (perf_counter_ns() - t_pat_0) / 1e6
        if pattern_match:
            # Resolve relative folder references if list_directory
            if pattern_match.intent == "list_directory" and pattern_match.slots.get("path") in ("that folder", "the folder", "same folder", "that directory", "same directory") and self.reference_resolver:
                res = self.reference_resolver.resolve(str(pattern_match.slots["path"]))
                if res and res.referent:
                    pattern_match.slots["path"] = str(res.referent)

            # Check if open_app was matched but target is actually a file / document
            if pattern_match.intent == "open_app" and "name" in pattern_match.slots:
                name_val = str(pattern_match.slots["name"]).strip().casefold()
                if any(name_val.endswith(ext) for ext in (".pdf", ".docx", ".doc", ".txt", ".xlsx", ".csv", ".png", ".jpg", ".zip")) or name_val in ("that pdf", "the pdf", "this pdf", "that file", "the file", "this file", "that document", "the document", "this document"):
                    pattern_match.intent = "open_file"
                    pattern_match.slots = {"path": pattern_match.slots.pop("name")}

            # Check app disambiguation if open_app
            if pattern_match.intent == "open_app" and "name" in pattern_match.slots:
                ambig = disambiguate_app(pattern_match.slots["name"], self.app_resolver, request_id, routing_text)
                if ambig:
                    ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
                    ambig.breakdown_ms = breakdown
                    self._record(ambig)
                    return ambig

            # Check deictic file references and safety for open_file / delete_file
            if pattern_match.intent in ("delete_file", "open_file") and "path" in pattern_match.slots:
                path_val = str(pattern_match.slots["path"]).strip()
                path_lower = path_val.casefold()
                is_deictic = (
                    path_lower in ("the file", "the document", "the pdf", "the spreadsheet", "the report", "file", "document",
                                   "screenshot", "the screenshot", "that screenshot", "this screenshot",
                                   "that file", "that document", "that pdf", "that spreadsheet", "that report", "this file", "this pdf")
                    or path_lower.startswith(("that ", "this ", "the "))
                )
                if is_deictic:
                    if self.reference_resolver:
                        res = self.reference_resolver.resolve(path_val)
                        if res and res.referent and res.confidence == ReferenceConfidence.HIGH:
                            pattern_match.slots["path"] = str(res.referent)
                            is_deictic = False
                        elif res and res.confidence == ReferenceConfidence.AMBIGUOUS:
                            clarify_msg = res.clarification_prompt or f"Which {path_val} do you mean?"
                            ambig_dec = RouteDecision(
                                request_id=request_id,
                                lane=RouteLane.CLARIFY,
                                intent=pattern_match.intent,
                                slots={},
                                confidence=0.5,
                                source=RouteSource.EXACT,
                                complexity=ComplexityLevel.SIMPLE,
                                clarification=clarify_msg,
                                normalized_text=routing_text,
                                reason_code=ReasonCode.LOW_CONFIDENCE,
                                routing_ms=(perf_counter_ns() - t0) / 1e6,
                                breakdown_ms=breakdown,
                            )
                            self._record(ambig_dec)
                            return ambig_dec

                    if is_deictic:
                        type_word = path_lower.split()[-1]
                        type_display = type_word.upper() if type_word in ("pdf", "doc") else type_word
                        clarify_msg = f"Which {type_display} do you mean?" if type_display in ("PDF", "DOC", "document", "file", "spreadsheet", "report", "screenshot") else f"Which file would you like me to {pattern_match.intent.split('_')[0]}?"
                        ambig_file = RouteDecision(
                            request_id=request_id,
                            lane=RouteLane.CLARIFY,
                            intent=pattern_match.intent,
                            slots={},
                            confidence=0.5,
                            source=RouteSource.EXACT,
                            complexity=ComplexityLevel.SIMPLE,
                            clarification=clarify_msg,
                            normalized_text=routing_text,
                            reason_code=ReasonCode.LOW_CONFIDENCE,
                            routing_ms=(perf_counter_ns() - t0) / 1e6,
                            breakdown_ms=breakdown,
                        )
                        self._record(ambig_file)
                        return ambig_file

            # Check send_whatsapp_message without message body
            if pattern_match.intent == "send_whatsapp_message" and not pattern_match.slots.get("message"):
                ambig_msg = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.CLARIFY,
                    intent="clarify",
                    slots=pattern_match.slots,
                    confidence=0.5,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    clarification=f"What message would you like to send to {pattern_match.slots.get('recipient', 'the recipient')}?",
                    normalized_text=routing_text,
                    reason_code=ReasonCode.LOW_CONFIDENCE,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self._record(ambig_msg)
                return ambig_msg

            pattern_match.routing_ms = (perf_counter_ns() - t0) / 1e6
            pattern_match.breakdown_ms = breakdown
            if pattern_match.lane == RouteLane.LANE_0:
                self.cache.put(routing_text, pattern_match, self.registry_version)
            self._record(pattern_match)
            return pattern_match

        # 8b. DIRECT APP / TARGET RESOLUTION (e.g. "chrome", "notepad", "calc", "youtube", Start menu apps)
        if len(tokens) <= 4:
            from jarvis.tools.system.app_resolver import ALIASES, SYNONYMS, WEB_SERVICES
            direct_name = None
            if routing_text in ALIASES or routing_text in SYNONYMS or routing_text in WEB_SERVICES:
                direct_name = routing_text
            elif self.app_resolver:
                try:
                    if routing_text in getattr(self.app_resolver, "cache", {}):
                        direct_name = routing_text
                    elif hasattr(self.app_resolver, "resolve"):
                        target = self.app_resolver.resolve(routing_text)
                        if target:
                            direct_name = routing_text
                except Exception:
                    pass

            if direct_name:
                app_decision = RouteDecision(
                    request_id=request_id,
                    lane=RouteLane.LANE_0,
                    intent="open_app",
                    slots={"name": direct_name},
                    confidence=1.0,
                    source=RouteSource.EXACT,
                    complexity=ComplexityLevel.SIMPLE,
                    normalized_text=routing_text,
                    reason_code=ReasonCode.EXACT_PATTERN,
                    routing_ms=(perf_counter_ns() - t0) / 1e6,
                    breakdown_ms=breakdown,
                )
                self.cache.put(routing_text, app_decision, self.registry_version)
                self._record(app_decision)
                return app_decision

        # 9. PREFILTERED FUZZY MATCH
        t_fuzz_0 = perf_counter_ns()
        fuzzy = match_fuzzy(routing_text, candidate_names, self.catalog, request_id)
        breakdown["fuzzy_ms"] = (perf_counter_ns() - t_fuzz_0) / 1e6
        if fuzzy:
            if fuzzy.intent == "open_app" and "name" in fuzzy.slots:
                ambig = disambiguate_app(fuzzy.slots["name"], self.app_resolver, request_id, routing_text)
                if ambig:
                    ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
                    ambig.breakdown_ms = breakdown
                    self._record(ambig)
                    return ambig

            fuzzy.routing_ms = (perf_counter_ns() - t0) / 1e6
            fuzzy.breakdown_ms = breakdown
            if fuzzy.lane == RouteLane.LANE_0:
                self.cache.put(routing_text, fuzzy, self.registry_version)
            self._record(fuzzy)
            return fuzzy

        # 10. COMPLEXITY GATE
        t_cplx_0 = perf_counter_ns()
        complexity = check_complexity_gate(routing_text, request_id)
        breakdown["complexity_ms"] = (perf_counter_ns() - t_cplx_0) / 1e6
        if complexity:
            complexity.routing_ms = (perf_counter_ns() - t0) / 1e6
            complexity.breakdown_ms = breakdown
            self._record(complexity)
            return complexity

        # 10.5. LANE 0.75: SEMANTIC CAPABILITY RETRIEVAL & SLOT EXTRACTION (< 1 ms)
        t_cap_0 = perf_counter_ns()
        from jarvis.core.capabilities.slot_extractor import extract_slots
        top_caps = self.capability_retriever.retrieve(routing_text, top_k=3, min_score=6.0)
        breakdown["capability_retrieval_ms"] = (perf_counter_ns() - t_cap_0) / 1e6
        if top_caps:
            best_cap, score = top_caps[0]
            second_score = top_caps[1][1] if len(top_caps) > 1 else 0.0
            anchored = getattr(self.capability_retriever, "anchored", lambda *_: True)(best_cap, routing_text) \
                and self._retrieval_ok(best_cap.target_tool, routing_text)
            if anchored and (score >= 8.5 or (score >= 6.0 and (score - second_score) >= 2.5)):
                slots, missing = extract_slots(best_cap, routing_text, self.working_memory, self.reference_resolver)
                if not missing:
                    cap_dec = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_0,
                        intent=best_cap.target_tool,
                        slots=slots,
                        confidence=min(1.0, score / 20.0),
                        source=RouteSource.EXACT,
                        complexity=ComplexityLevel.SIMPLE,
                        normalized_text=routing_text,
                        reason_code=ReasonCode.EXACT_PATTERN,
                        routing_ms=(perf_counter_ns() - t0) / 1e6,
                        breakdown_ms=breakdown,
                    )
                    self.cache.put(routing_text, cap_dec, self.registry_version)
                    self._record(cap_dec)
                    return cap_dec
                elif score >= 12.0:
                    from jarvis.core.router.ollama import DisabledProvider
                    if isinstance(self.llm_provider, DisabledProvider):
                        slot_names = ", ".join(missing)
                        clarification = f"Could you please specify the {slot_names} to {best_cap.description.lower().rstrip('.')}?"
                        clarify_dec = RouteDecision(
                            request_id=request_id,
                            lane=RouteLane.CLARIFY,
                            intent=best_cap.target_tool,
                            slots=slots,
                            confidence=0.5,
                            source=RouteSource.EXACT,
                            complexity=ComplexityLevel.SIMPLE,
                            clarification=clarification,
                            normalized_text=routing_text,
                            reason_code=ReasonCode.LOW_CONFIDENCE,
                            candidate_count=len(top_caps),
                            routing_ms=(perf_counter_ns() - t0) / 1e6,
                            breakdown_ms=breakdown,
                        )
                        self._record(clarify_dec)
                        return clarify_dec

        # 11. LANE 1: TINY LOCAL MODEL (Ollama)
        # One step of a multi-step request (the planner handles the whole request), or a live preview while the user
        # is still speaking: never wait for (or load) a model here.
        if _IN_CLAUSE.get() or _NO_MODEL.get():
            return RouteDecision(request_id=request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.5,
                                 source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.COMPLEX, needs_planner=True,
                                 normalized_text=routing_text, reason_code=ReasonCode.MULTI_STEP, candidate_count=0)
        candidate_defns = [self.catalog.intents[c] for c in candidate_names if c in self.catalog.intents]
        try:
            llm_decision = await self.llm_provider.classify(routing_text, candidate_defns, request_id)
        except Exception as exc:
            llm_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.CLARIFY,
                intent=None,
                slots={},
                confidence=0.0,
                source=RouteSource.TINY_MODEL,
                complexity=ComplexityLevel.SIMPLE,
                clarification=f"classifier_error: {type(exc).__name__}",
                normalized_text=routing_text,
                reason_code=ReasonCode.UNKNOWN_INTENT,
            )

        llm_decision.routing_ms = (perf_counter_ns() - t0) / 1e6
        breakdown.update(llm_decision.breakdown_ms)
        llm_decision.breakdown_ms = breakdown

        # Verify app disambiguation if Lane 1 chose open_app
        if llm_decision.intent == "open_app" and "name" in llm_decision.slots:
            ambig = disambiguate_app(str(llm_decision.slots["name"]), self.app_resolver, request_id, routing_text)
            if ambig:
                ambig.routing_ms = (perf_counter_ns() - t0) / 1e6
                ambig.breakdown_ms = breakdown
                self._record(ambig)
                return ambig

        # If unclassified by tiny model, escalate to Lane 0 or Lane 2 if capabilities match
        if llm_decision.lane == RouteLane.CLARIFY and not llm_decision.intent:
            sem_caps = self.capability_retriever.retrieve(routing_text, top_k=2, min_score=6.0)
            if sem_caps:
                best_cap, score = sem_caps[0]
                if score >= 6.0 and getattr(self.capability_retriever, "anchored", lambda *_: True)(best_cap, routing_text) \
                        and self._retrieval_ok(best_cap.target_tool, routing_text):
                    from jarvis.core.capabilities.slot_extractor import extract_slots
                    slots, missing = extract_slots(best_cap, routing_text, self.working_memory, self.reference_resolver)
                    if not missing:
                        llm_decision = RouteDecision(
                            request_id=request_id,
                            lane=RouteLane.LANE_0,
                            intent=best_cap.target_tool,
                            slots=slots,
                            confidence=min(1.0, score / 20.0),
                            source=RouteSource.EXACT,
                            complexity=ComplexityLevel.SIMPLE,
                            normalized_text=routing_text,
                            reason_code=ReasonCode.EXACT_PATTERN,
                            routing_ms=(perf_counter_ns() - t0) / 1e6,
                            breakdown_ms=breakdown,
                        )
                        self.cache.put(routing_text, llm_decision, self.registry_version)
                        self._record(llm_decision)
                        return llm_decision

            # If multi-step or planner required
            if not _llm_down(llm_decision):
                sem_caps_low = self.capability_retriever.retrieve(routing_text, top_k=1, min_score=4.0)
                if sem_caps_low:
                    llm_decision = RouteDecision(
                        request_id=request_id,
                        lane=RouteLane.LANE_2,
                        intent=None,
                        slots={},
                        confidence=0.85,
                        source=RouteSource.COMPLEXITY_GATE,
                        complexity=ComplexityLevel.COMPLEX,
                        needs_planner=True,
                        normalized_text=routing_text,
                        reason_code=ReasonCode.MULTI_STEP,
                    )

        # If LLM classified as unknown or clarify, route to dynamic Ollama chat unless model is unavailable or disabled!
        from jarvis.core.router.ollama import DisabledProvider
        if not isinstance(self.llm_provider, DisabledProvider) and llm_decision.lane == RouteLane.CLARIFY and not llm_decision.intent and not _llm_down(llm_decision):
            llm_decision = RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent="ollama_chat",
                slots={"query": original_text},
                confidence=0.95,
                source=RouteSource.TINY_MODEL,
                complexity=ComplexityLevel.SIMPLE,
                normalized_text=routing_text,
                reason_code=ReasonCode.LLM_CLASSIFIED,
                routing_ms=(perf_counter_ns() - t0) / 1e6,
                breakdown_ms=breakdown,
                # Not a question and no single tool matched: the service hands this to the tool-using agent.
                context_trace={"fallback": "unknown_command"},
            )

        self._record(llm_decision)
        return llm_decision

    # A later step starts with one of these (after "and", "then" or a comma); the text before it is a separate step.
    _STEP_VERBS = (r"open|launch|start|close|quit|exit|type|write|play|pause|resume|stop|set|turn|mute|unmute|increase|"
                   r"decrease|lower|raise|search|google|look up|take|paste|copy|cut|select|press|hit|save|go to|scroll|"
                   r"minimize|maximize|show|lock|refresh|reload|switch|send|share|make|create|move|delete|rename|download|"
                   r"install|read|summarize|check|find|call|message|text|remind|note|bookmark|zoom|screenshot|snip|put|"
                   r"click|enable|disable|connect|fill|autofill|dictate|shut down|restart|sleep|empty|clear|dim|brighten|crank|reduce|"
                   r"upload|launch|kill|unlock")
    _FIRST_VERBS = _STEP_VERBS + r"|research|compare|book|order|translate"
    _MESSAGE_WORDS = re.compile(r"\b(?:saying|says|tell|text|message|reply|remind|note that|write that|whatsapp|email|mail|sms)\b")

    def _split_steps(self, text: str) -> list[str]:
        t = " ".join(text.strip().rstrip(".!?").split())
        verbs = self._STEP_VERBS
        # "open youtube and play X" is one step: play X on YouTube
        t = re.sub(r"^(?:open|go to|launch)\s+youtube\s+(?:and\s+)?(?:then\s+)?play\s+(.+?)(?=\s*(?:,|\band then\b|\bthen\b|\band\s+(?:"
                   + verbs + r")\b|$))", r"play \1 on youtube", t, flags=re.I)
        # "close chrome and edge" -> close chrome ; close edge
        m = re.match(r"^(close|quit|exit|kill)\s+([a-z0-9 .+-]+?(?:\s*(?:,|\band\b)\s*[a-z0-9 .+-]+?)+)$", t, flags=re.I)
        if m and not re.search(r"\bnot\b", m.group(2), flags=re.I) and not re.search(rf"(?:,|\band\b)\s*(?:{verbs})\b", m.group(2), flags=re.I):
            names = [n.strip() for n in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", m.group(2)) if n.strip()]
            t = " ; ".join(f"{m.group(1)} {n}" for n in names)
        t = re.sub(rf"\s*,?\s*\b(?:and\s+)?then\b\s*,?\s*(?=(?:{verbs})\b)", " ; ", t, flags=re.I)
        t = re.sub(rf"\s*,\s*(?:and\s+)?(?=(?:{verbs})\b)", " ; ", t, flags=re.I)
        t = re.sub(rf"\s+and\s+(?=(?:{verbs})\b)", " ; ", t, flags=re.I)
        return [c.strip(" ,") for c in t.split(";") if c.strip(" ,")]

    async def _route_multi_step(self, text: str, request_id: str) -> RouteDecision | None:
        lowered = " ".join(text.lower().split())
        if not re.search(r"\band\b|\bthen\b|,", lowered):
            return None
        lowered = re.sub(r"^(?:(?:please|kindly|jarvis\s*,?|(?:can|could|would|will)\s+(?:you|u)|first(?:ly)?\s*,?|to start\s*,?)\s+)+", "", lowered)
        if not re.match(rf"^(?:{self._FIRST_VERBS})\b", lowered):
            return None
        commands_part = re.split(r"\b(?:type|write|saying)\b", lowered, maxsplit=1)[0]  # typed text is the user's words
        if re.search(r"\b(?:wait|sorry|actually|i mean|instead|rather|no no|scratch that)\b|\bno\s*,|\band not\b|,\s*not\b|\bbut\s+not\b|\brather\s+than\b|\binstead\s+of\b|\b(?:if (?:you're|you are) not sure|ask me|clarify)\b", commands_part):
            return None  # a correction or negation or ambiguity directive, not a list of steps
        # one action that reads like two ("take a screenshot and paste it in whatsapp", "copy this and paste in notepad")
        from jarvis.core.router.extended import match_extended
        whole = match_extended(text, request_id)
        if whole and whole.intent == "pc_quick_action" and (whole.slots or {}).get("action") in (
                "screenshot_paste", "copy_paste_to_app", "paste_to_app"):
            return None
        if whole and (whole.intent in ("create_shortcut", "reply_whatsapp_all", "whatsapp_auto_reply", "calendar_create_event",
                                       "gmail_create_draft", "install_software")
                      or (whole.intent == "screen_click" and re.search(r"\b(?:click|tap|press|select)\s+(?:on\s+)?(?:it|that)$", lowered))):
            return None  # one action whose wording contains several verbs ("find the wifi icon and click it")
        text = re.sub(r"^(?:(?:please|kindly|jarvis\s*,?|(?:can|could|would|will)\s+(?:you|u)|first(?:ly)?\s*,?|to start\s*,?)\s+)+", "", text.strip(), flags=re.I)
        steps = self._split_steps(text)  # original casing: typed text keeps the user's capitals
        if not 2 <= len(steps) <= 5:
            return None
        # a message's own words ("tell mom I'll come and then call") belong to the message, not to new steps
        first = steps[0].lower()
        if self._MESSAGE_WORDS.search(first) and not re.fullmatch(r"(?:open|launch|start|close|quit|exit|kill)\s+(?:the\s+)?whats\s*app(?:\s+(?:app|web|desktop))?", first):
            return None  # "open whatsapp" is the app, not a message
        subs: list[SubCommand] = []
        risks: list[str] = []
        token = _IN_CLAUSE.set(True)
        try:
            for step in steps:
                d = await self.route(CommandRequest(text=step))
                if (d.lane != RouteLane.LANE_0 or not d.intent or d.subcommands or d.intent in self._NOT_STEP_INTENTS
                        or d.complexity == ComplexityLevel.COMPOUND):
                    subs = []
                    break
                subs.append(SubCommand(intent=d.intent, tool=d.intent, arguments=dict(d.slots or {})))
                risks.append(str(d.risk or "REVERSIBLE"))
        finally:
            _IN_CLAUSE.reset(token)
        if not subs:
            # at least one step needs thinking (research, find, decide): the planner/agent does the whole request
            return RouteDecision(
                request_id=request_id, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.95,
                source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.COMPLEX, needs_planner=True,
                normalized_text=lowered, reason_code=ReasonCode.MULTI_STEP, candidate_count=0)
        # "open notepad and type hello": type into the app that was just opened, once its window is up
        for prev, sub in zip(subs, subs[1:]):
            if prev.tool == "open_app" and sub.tool in ("dictate_text", "dictation_mode_control") and not sub.arguments.get("target_app"):
                sub.arguments["target_app"] = str(prev.arguments.get("name") or "")
        order = ("DESTRUCTIVE", "EXTERNAL_EFFECT", "SENSITIVE", "REVERSIBLE", "READ_ONLY")
        risk = next((r for r in order if r in risks), "REVERSIBLE")
        return RouteDecision(
            request_id=request_id, lane=RouteLane.LANE_0, intent="compound", slots={"steps": [s.tool for s in subs]},
            confidence=1.0, source=RouteSource.EXACT, complexity=ComplexityLevel.COMPOUND, risk=risk, missing_slots=[],
            normalized_text=lowered, reason_code=ReasonCode.COMPOUND_COMMAND, subcommands=subs, candidate_count=len(subs))

    _NOT_STEP_INTENTS = frozenset({"compound", "clarify", "show_dashboard", "stop_speaking", "stop_task", "cancel_task",
                                   "chat", "general_chat", "unsupported"})

    def _record(self, decision: RouteDecision):
        self.total_routed += 1
        if decision.lane.value in self.lane_counts:
            self.lane_counts[decision.lane.value] += 1
        if decision.lane == RouteLane.CLARIFY and "candidates" in decision.slots:
            self.last_clarification_candidates = list(decision.slots["candidates"])
            self.last_clarification_intent = str(decision.intent or "open_app")
        if self.trace_debug:
            print(
                f"[ROUTER TRACE] text='{decision.normalized_text}' lane={decision.lane} "
                f"intent={decision.intent} src={decision.source} ms={decision.routing_ms:.3f}ms",
                flush=True,
            )
