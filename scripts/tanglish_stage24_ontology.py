"""Coarse semantic families for an offline hierarchical model.

These labels do not select tools. Fine ActionConcept and typed slots remain
separate; object and context decide between neighboring concepts.
"""
from __future__ import annotations

from scripts.build_tanglish_stage21_repair import ACTION_MAP

FAMILIES = {
    "ACCESS": {"OPEN", "CLOSE", "NAVIGATE"},
    "INSPECT": {"SEARCH", "FIND", "SHOW", "LIST", "READ", "INSPECT", "CHECK", "VERIFY", "RETRIEVE"},
    "PROVIDE": {"PROVIDE", "ANSWER", "RETURN", "EXPLAIN", "SUMMARIZE"},
    "COMMUNICATE": {"SEND", "SHARE", "FORWARD", "REPLY", "CALL"},
    "CONTENT_EDIT": {"WRITE", "TYPE", "ENTER", "INSERT"},
    "RESOURCE_TRANSFER": {"MOVE", "COPY", "DOWNLOAD", "UPLOAD", "ATTACH"},
    "TRANSFORM": {"RENAME", "CONVERT", "CHANGE", "REPLACE", "SWITCH", "SET", "INCREASE", "DECREASE"},
    "LIFECYCLE": {"CREATE", "DELETE", "INSTALL", "UNINSTALL", "SAVE", "CANCEL"},
    "CONTROL": {"RUN", "START", "STOP", "PAUSE", "RESUME", "RESTART", "PLAY", "MUTE", "UNMUTE", "CLICK"},
    "SELECT_ORGANIZE": {"SELECT", "FILTER", "SORT"},
    "CAPTURE": {"CAPTURE"},
    "ANALYZE": {"COMPARE"},
    "EXTERNAL_TRANSACTION": {"SUBMIT", "PAY"},
}
ACTION_FAMILY = {action:family for family,actions in FAMILIES.items() for action in actions}
assert len(ACTION_FAMILY)==sum(len(actions) for actions in FAMILIES.values())
assert set(ACTION_FAMILY)==set(ACTION_MAP), (set(ACTION_MAP)-set(ACTION_FAMILY),set(ACTION_FAMILY)-set(ACTION_MAP))

SPEECH_COARSE={
    "COMMAND":"ACTION_ORIENTED", "CORRECTION":"ACTION_ORIENTED",
    "META_CONTROL":"ACTION_ORIENTED", "NEGATED_COMMAND":"ACTION_ORIENTED",
    "QUESTION":"NON_ACTION", "CAPABILITY_QUERY":"NON_ACTION",
    "STATEMENT":"NON_ACTION", "HYPOTHETICAL":"NON_ACTION", "CHAT":"NON_ACTION",
    "AMBIGUOUS":"UNCERTAIN",
}
