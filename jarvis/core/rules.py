"""Standing rules the owner gave ("don't create or send anything until I approve the preview").

A rule is kept until the owner clears it. Two kinds:

* ``approve_first``: enforced by the command service - every step that creates, sends or changes something waits
  for the owner's OK with a preview first, even ones that normally run straight away.
* any other rule: written into the planner and agent prompts as a rule they must obey.

Rules that JARVIS already enforces in code (groups, uncertain sends, message text is data, ...) are acknowledged but
not stored - there is nothing more to enforce.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional


class RuleBook:
    def __init__(self, path: Optional[Path] = None, persist: bool = True) -> None:
        self.path = Path(path) if path else None
        self.persist = persist
        self._lock = threading.Lock()
        self._rules: Optional[list[dict]] = None

    def _file(self) -> Optional[Path]:
        if not self.persist:
            return None
        if self.path is None:
            from jarvis.tools.system.everyday_tools import default_db_path
            self.path = default_db_path().parent / "standing_rules.json"
        return self.path

    def _load(self) -> list[dict]:
        if self._rules is None:
            self._rules = []
            f = self._file()
            try:
                if f is not None and f.exists():
                    data = json.loads(f.read_text(encoding="utf-8"))
                    self._rules = [r for r in data if isinstance(r, dict) and r.get("rule")]
            except Exception:
                self._rules = []
        return self._rules

    def _save(self) -> None:
        f = self._file()
        if f is None:
            return
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(self._rules or [], indent=1), encoding="utf-8")
        except OSError:
            pass

    def add(self, rule: str, topic: str = "custom") -> dict:
        with self._lock:
            rules = self._load()
            for r in rules:
                if r["rule"].lower() == rule.lower():
                    return r
            entry = {"rule": rule, "topic": topic, "at": time.time()}
            rules.append(entry)
            del rules[:-50]  # the newest 50 are plenty
            self._save()
            return entry

    def rules(self) -> list[dict]:
        with self._lock:
            return list(self._load())

    def clear(self) -> int:
        with self._lock:
            n = len(self._load())
            self._rules = []
            self._save()
            return n

    def requires_approval(self) -> bool:
        return any(r.get("topic") == "approve_first" for r in self.rules())

    def prompt_block(self) -> str:
        """The rules as a prompt section for the planner / agent ('' when there are none)."""
        rules = self.rules()
        if not rules:
            return ""
        return "Owner's standing rules (always obey them; they override the request when they conflict):\n" + \
            "\n".join(f"- {r['rule']}" for r in rules)


_book: Optional[RuleBook] = None


def get_rulebook() -> RuleBook:
    global _book
    if _book is None:
        import sys
        _book = RuleBook(persist="pytest" not in sys.modules)  # a test run never writes the owner's rule file
    return _book


def set_rulebook(book: Optional[RuleBook]) -> None:
    global _book
    _book = book
