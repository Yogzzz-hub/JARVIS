"""Deterministic rule signals + compact context vector, appended to the text embedding.

These are *signals*, not routes: each is a weak, general cue (sentence form, verbs, references,
freshness words, device nouns...). The classifier heads learn how much to trust each one.
No sentence-specific patterns live here.
"""
from __future__ import annotations

import re

import numpy as np

from jarvis.decision.schemas import ROUTE_FAMILIES, DecisionState

_W = lambda words: re.compile(r"\b(?:" + words + r")\b", re.I)  # noqa: E731

SIGNALS: list[tuple[str, re.Pattern]] = [
    ("q_word_start", re.compile(r"^\s*(?:what|who|whom|whose|why|how|when|where|which|is|are|was|were|do|does|did|can|could|should|would|will|explain|define|tell me about|describe)\b", re.I)),
    ("question_mark", re.compile(r"\?\s*$")),
    ("imperative_start", re.compile(r"^\s*(?:please\s+|pls\s+|hey\s+jarvis,?\s+|jarvis,?\s+|can you\s+|could you\s+|would you\s+)?(?:open|close|launch|start|stop|run|play|pause|resume|skip|send|reply|text|message|tell|ask|remind|set|turn|switch|mute|unmute|find|search|look up|show|list|read|copy|move|delete|remove|rename|create|make|install|uninstall|update|download|upload|take|click|press|type|go|navigate|book|call|dial|lock|share|transfer|pull|push|get|bring|summari[sz]e|organi[sz]e|check|schedule|add|write|draft|translate)\b", re.I)),
    ("how_do_i", re.compile(r"\bhow (?:do|can|would|should) (?:i|you|we)\b|\bhow to\b", re.I)),
    ("what_is", re.compile(r"\bwhat(?:'s| is| are| does| do)\b", re.I)),
    ("can_i_question", re.compile(r"^\s*(?:(?:can|should|could|would|may) (?:i|we)|is it (?:possible|safe|okay|ok|bad|good|wise|legal) to|what happens if (?:i|we)|is there a (?:way|shortcut) to|why (?:can't|cannot|won't) (?:i|we))\b", re.I)),
    ("about_product", re.compile(r"^\s*(?:what(?:'s| is| are)|tell me about|explain|describe)\s+(?:a |an |the )?[a-z0-9 .+-]{2,30}\??\s*$", re.I)),
    ("negation", re.compile(r"\b(?:don'?t|do not|never|no need to|stop|without|instead of|not)\b", re.I)),
    ("draft_only", _W(r"draft|preview|write up|compose but|don'?t send|do not send")),
    ("multi_clause", re.compile(r"\b(?:and then|then|after that|afterwards|once (?:that|it)|finally|also|and)\b.*\b(?:open|send|search|find|save|compare|summari[sz]e|download|play|tell|check|email|message|copy|move)\b", re.I)),
    ("conditional", _W(r"if|unless|in case|whenever|only if|otherwise")),
    ("compare", _W(r"compare|versus|vs|difference between|better than|pros and cons")),
    ("pronoun_ref", _W(r"it|that|this|these|those|them|him|her|he|she|they|the same|that one|this one")),
    ("deictic_recent", _W(r"just found|i just|earlier|previous|last one|the one|from before|you found|from yesterday|that file")),
    ("fresh_info", _W(r"latest|newest|today|tonight|right now|current|currently|news|weather|forecast|score|price|stock|live|this week|yesterday|trending|release|recent")),
    ("my_docs", _W(r"my (?:notes|documents|docs|files|pdfs?|papers|resume|cv|slides|report|knowledge base)|according to my|in my notes|from my notes")),
    ("file_words", _W(r"file|files|folder|folders|pdf|pdfs|docx?|document|documents|spreadsheet|downloads|desktop|drive [a-z]|directory|zip")),
    ("whatsapp_word", _W(r"whats ?app|wa")),
    ("message_verbs", _W(r"message|text|reply|dm|ping|chat|messaged|texted")),
    ("person_verbs", _W(r"tell|ask|remind|inform|let .+ know|wish")),
    ("phone_words", _W(r"phone|mobile|android|smartphone")),
    ("transfer_words", _W(r"to my (?:phone|pc|laptop|computer)|from my (?:phone|pc|laptop|computer)|transfer|localsend|airdrop|send .* to (?:my )?(?:phone|laptop|pc)")),
    ("browser_words", _W(r"browser|website|site|web ?page|tab|url|chrome tab|google|youtube|amazon|flipkart|wikipedia|github|linkedin|form|log ?in|sign ?in")),
    ("screen_words", _W(r"screen|button|click|window|dialog|popup|menu|icon|toolbar|field|checkbox")),
    ("media_words", _W(r"song|music|playlist|video|track|spotify|podcast|volume|pause|resume|skip|next|previous")),
    ("system_words", _W(r"volume|brightness|wifi|wi-fi|bluetooth|battery|cpu|ram|memory|disk|shutdown|restart|sleep|lock|time|date|settings|night light|dark mode|screenshot")),
    ("google_words", _W(r"gmail|email|e-mail|inbox|calendar|meeting|event|google drive|drive")),
    ("reminder_words", _W(r"remind me|reminder|alarm|timer|note|to-?do|todo|in \d+ minutes|at \d+")),
    ("package_words", _W(r"install|uninstall|reinstall|update|upgrade|winget|setup|download and install")),
    ("dev_words", _W(r"code|git|commit|repo|repository|terminal|powershell|python|script|function|bug|test|compile|build|npm|pip")),
    ("workflow_words", _W(r"routine|briefing|workspace|morning|focus mode|study mode|daily")),
    ("app_names", _W(r"chrome|edge|firefox|notepad|calculator|calc|word|excel|powerpoint|vs ?code|visual studio|spotify|discord|telegram|teams|zoom|explorer|paint|vlc|obs|steam|outlook|slack")),
    ("external_verbs", _W(r"send|reply|post|publish|email|mail|submit|share|forward|tweet|upload|book|order|pay|buy|purchase|transfer money")),
    ("destructive_verbs", _W(r"delete|remove|erase|wipe|format|uninstall|shred|empty (?:the )?(?:recycle|trash)|kill|terminate|factory reset|shut ?down|restart")),
    ("vague_object", re.compile(r"^\s*(?:(?:please\s+)?(?:open|send|delete|close|play|show|do|fix|move|copy|click)\s+(?:it|that|this|them|him|her|the thing|something|stuff)(?:\s+(?:to|for)\s+(?:him|her|them))?)\s*[.!?]?\s*$", re.I)),
    ("very_short", re.compile(r"^\s*\S+(?:\s+\S+)?\s*[.!?]?\s*$")),
    ("url_present", re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|org|net|io|in|dev|ai)\b", re.I)),
    ("number_present", re.compile(r"\d")),
    ("greeting_smalltalk", re.compile(r"^\s*(?:hi|hello|hey|thanks|thank you|good (?:morning|night|evening)|how are you|who are you|what can you do|tell me a joke)\b", re.I)),
    ("gibberish", re.compile(r"^[^aeiou\s]{6,}$|(?:\b\w\b\s*){5,}", re.I)),
]

CONTEXT_RESOURCES = ("FileResource", "ContactResource", "MediaResource", "ApplicationResource", "UrlResource",
                     "MessageResource", "ResultSet", "TopicRef")

FEATURE_NAMES: list[str] = (
    [name for name, _ in SIGNALS]
    + ["n_words_log", "n_clauses"]
    + [f"res:{r}" for r in CONTEXT_RESOURCES]
    + ["ctx:topic", "ctx:pending_confirmation", "ctx:pending_task", "ctx:current_app"]
    + [f"prev:{f}" for f in ROUTE_FAMILIES]
    + ["chan:whatsapp", "chan:voice"]
)


def rule_features(state: DecisionState) -> np.ndarray:
    text = state.text or ""
    vec = [1.0 if pat.search(text) else 0.0 for _, pat in SIGNALS]
    words = len(text.split())
    clauses = len(re.findall(r",|\band\b|\bthen\b|;", text, re.I))
    vec += [float(np.log1p(words)) / 3.0, min(clauses, 5) / 5.0]
    vec += [1.0 if r in state.resources else 0.0 for r in CONTEXT_RESOURCES]
    vec += [1.0 if state.active_topic_type else 0.0, 1.0 if state.pending_confirmation else 0.0,
            1.0 if state.pending_task else 0.0, 1.0 if state.current_app else 0.0]
    vec += [1.0 if state.previous_route == f else 0.0 for f in ROUTE_FAMILIES]
    vec += [1.0 if state.channel.startswith("whatsapp") else 0.0, 1.0 if "voice" in state.channel else 0.0]
    return np.asarray(vec, dtype=np.float32)

