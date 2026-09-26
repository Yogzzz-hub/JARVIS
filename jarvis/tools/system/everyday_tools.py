"""Everyday assistant tools that run instantly and offline (no LLM on the hot path).

* ``quick_answer``      - calculator, percentages, unit/temperature conversion, date maths, world clock,
                          coin flip / dice / random numbers. Answers in well under a millisecond.
* ``battery_status``    - battery level, charging state and time left.
* ``network_info``      - host name, local IP, Wi-Fi network, internet reachability.
* ``stopwatch``         - start / lap / stop / reset a stopwatch.
* ``todo``              - a to-do list stored in the JARVIS SQLite database.
* ``remember_fact`` / ``recall_facts`` / ``forget_fact`` - personal facts stored in SQLite and indexed into the
                          knowledge base (RAG), so grounded chat answers can use them.
* ``create_shortcut`` / ``list_shortcuts`` / ``delete_shortcut`` - voice macros ("when I say goodnight, lock the
                          PC and mute"). The command service expands a shortcut into its steps; every step is routed
                          and policy-checked like a normal command.
* ``command_history``   - what you asked recently (from the requests table).
* ``generate_password`` - a strong random password copied to the clipboard (never spoken or stored).
* ``empty_recycle_bin`` - destructive: policy always asks for confirmation.
"""
from __future__ import annotations

import ast
import json
import logging
import math
import operator
import os
import random
import re
import secrets
import socket
import sqlite3
import string
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import Field

from jarvis.config import ROOT
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.everyday")


# ============================================================================ quick answers (pure functions)

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {"sqrt": math.sqrt, "sin": lambda x: math.sin(math.radians(x)), "cos": lambda x: math.cos(math.radians(x)),
          "tan": lambda x: math.tan(math.radians(x)), "log": math.log10, "ln": math.log, "abs": abs, "round": round,
          "factorial": math.factorial}
_CONSTS = {"pi": math.pi, "e": math.e}


def safe_eval(expr: str) -> float:
    """Evaluate arithmetic only (numbers, + - * / // % **, a few math functions). Never eval()."""
    node = ast.parse(expr, mode="eval").body

    def ev(n: ast.AST) -> float:
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name) and n.id in _CONSTS:
            return _CONSTS[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            left, right = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(right) > 100 or abs(left) > 1e6):
                raise ValueError("exponent too large")
            return _OPS[type(n.op)](left, right)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and len(n.args) == 1:
            arg = ev(n.args[0])
            if n.func.id == "factorial" and (arg > 170 or arg != int(arg)):
                raise ValueError("factorial too large")
            return _FUNCS[n.func.id](int(arg) if n.func.id == "factorial" else arg)
        raise ValueError("unsupported expression")

    return ev(node)


def fmt_number(x: float) -> str:
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, int) or (isinstance(x, float) and x.is_integer() and abs(x) < 1e15):
        return f"{int(x):,}"
    if abs(x) >= 1e15 or (abs(x) < 1e-4 and x != 0):
        return f"{x:.4g}"
    return f"{x:,.4f}".rstrip("0").rstrip(".")


_WORD_OPS = [
    (r"\bmultiplied by\b|\btimes\b|\bx\b(?=\s*[\d(])|×", "*"), (r"\bdivided by\b|\bover\b|÷", "/"),
    (r"\bplus\b|\badd\b", "+"), (r"\bminus\b|\bsubtract\b", "-"), (r"\bmod(?:ulo)?\b", "%"),
    (r"\bto the power of\b|\braised to\b|\^", "**"), (r"\bsquared\b", "**2"), (r"\bcubed\b", "**3"),
    (r"\bsquare root of\b", "sqrt "), (r"\bthe\b", ""),
]

_CALC_PREFIX = re.compile(r"^(?:what(?:'s| is)|whats|calculate|compute|how much is|solve|evaluate|work out|tell me)\s+", re.I)


def _math_expression(text: str) -> Optional[str]:
    t = _CALC_PREFIX.sub("", text.strip().lower().rstrip("?.! ="))
    t = re.sub(r"^(?:what(?:'s| is)|calculate)\s+", "", t)
    for pat, rep in _WORD_OPS:
        t = re.sub(pat, rep, t)
    t = re.sub(r"(\d),(\d{3})", r"\1\2", t)
    t = re.sub(r"\bsqrt\s+(\d+(?:\.\d+)?)", r"sqrt(\1)", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*!", r"factorial(\1)", t)
    t = re.sub(r"(\d+)\s+factorial\b", r"factorial(\1)", t)
    t = re.sub(r"\bfactorial (?:of )?(\d+)", r"factorial(\1)", t)
    t = t.strip()
    if not t or not re.search(r"\d", t) or not re.fullmatch(r"[\d\s.+\-*/%()a-z]+", t):
        return None
    words = set(re.findall(r"[a-z]+", t))
    if words - set(_FUNCS) - set(_CONSTS):
        return None
    if not re.search(r"[+\-*/%]|\b(?:sqrt|sin|cos|tan|log|ln|factorial)\b", t):
        return None
    return t


# Unit conversion: factor to a base unit per dimension.
_UNITS: dict[str, tuple[str, float]] = {}


def _add_units(dim: str, table: dict[str, float]) -> None:
    for names, factor in table.items():
        for name in names.split("|"):
            _UNITS[name] = (dim, factor)


_add_units("length", {"mm|millimeter|millimeters|millimetre|millimetres": 0.001, "cm|centimeter|centimeters|centimetre|centimetres": 0.01,
                      "m|meter|meters|metre|metres": 1.0, "km|kilometer|kilometers|kilometre|kilometres": 1000.0,
                      "in|inch|inches": 0.0254, "ft|foot|feet": 0.3048, "yd|yard|yards": 0.9144, "mi|mile|miles": 1609.344})
_add_units("mass", {"mg|milligram|milligrams": 1e-6, "g|gram|grams": 0.001, "kg|kilo|kilos|kilogram|kilograms": 1.0,
                    "t|tonne|tonnes|ton|tons": 1000.0, "lb|lbs|pound|pounds": 0.45359237, "oz|ounce|ounces": 0.028349523125})
_add_units("volume", {"ml|milliliter|milliliters|millilitre|millilitres": 0.001, "l|liter|liters|litre|litres": 1.0,
                      "gallon|gallons|gal": 3.785411784, "cup|cups": 0.2365882365, "pint|pints": 0.473176473,
                      "tablespoon|tablespoons|tbsp": 0.0147867648, "teaspoon|teaspoons|tsp": 0.00492892159})
_add_units("speed", {"kmh|kph|km/h|kilometers per hour|kilometres per hour": 1 / 3.6, "mph|miles per hour": 0.44704,
                     "m/s|meters per second|metres per second": 1.0, "knot|knots": 0.514444})
_add_units("data", {"b|byte|bytes": 1.0, "kb|kilobyte|kilobytes": 1024.0, "mb|megabyte|megabytes": 1024.0 ** 2,
                    "gb|gigabyte|gigabytes": 1024.0 ** 3, "tb|terabyte|terabytes": 1024.0 ** 4})
_add_units("time", {"ms|millisecond|milliseconds": 0.001, "s|sec|secs|second|seconds": 1.0, "min|mins|minute|minutes": 60.0,
                    "h|hr|hrs|hour|hours": 3600.0, "day|days": 86400.0, "week|weeks": 604800.0, "year|years": 31557600.0})
_add_units("area", {"sqm|square meter|square meters|square metre|square metres": 1.0, "sqft|square foot|square feet": 0.09290304,
                    "acre|acres": 4046.8564224, "hectare|hectares|ha": 10000.0})
_TEMPS = {"c": "c", "celsius": "c", "centigrade": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}

_UNIT_RE = "|".join(sorted((re.escape(u) for u in list(_UNITS) + list(_TEMPS)), key=len, reverse=True))
_CONVERT = re.compile(
    rf"^(?:convert\s+|how many\s+(?P<to1>{_UNIT_RE})\s+(?:is|are|in)\s+|what(?:'s| is)\s+)?"
    rf"(?P<n>-?\d+(?:\.\d+)?)\s*(?:degrees?\s+)?(?P<from>{_UNIT_RE})"
    rf"(?:\s+(?:to|in|into|as)\s+(?:degrees?\s+)?(?P<to2>{_UNIT_RE}))?$", re.I)


def convert_units(text: str) -> Optional[str]:
    t = re.sub(r"\s+", " ", text.strip().lower().rstrip("?.! "))
    m = _CONVERT.match(t)
    if not m or not (m.group("to1") or m.group("to2")):
        return None
    n, src, dst = float(m.group("n")), m.group("from"), (m.group("to1") or m.group("to2"))
    if src in _TEMPS and dst in _TEMPS:
        a, b = _TEMPS[src], _TEMPS[dst]
        c = n if a == "c" else (n - 32) * 5 / 9 if a == "f" else n - 273.15
        out = c if b == "c" else c * 9 / 5 + 32 if b == "f" else c + 273.15
        label = {"c": "°C", "f": "°F", "k": "K"}
        return f"{fmt_number(n)}{label[a]} is {fmt_number(round(out, 2))}{label[b]}."
    if src not in _UNITS or dst not in _UNITS:
        return None
    (d1, f1), (d2, f2) = _UNITS[src], _UNITS[dst]
    if d1 != d2:
        return None
    value = n * f1 / f2
    return f"{fmt_number(n)} {src} is {fmt_number(round(value, 4))} {dst}."


_PERCENT = re.compile(r"^(?:what(?:'s| is)\s+)?(?P<p>\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(?P<n>\d+(?:\.\d+)?)$", re.I)
_TIP = re.compile(r"^(?:what(?:'s| is)\s+(?:a\s+)?)?(?P<p>\d+(?:\.\d+)?)\s*(?:%|percent)\s+tip\s+(?:on|for)\s+(?P<n>\d+(?:\.\d+)?)$", re.I)

_TZ = {
    "london": "Europe/London", "uk": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "new york": "America/New_York", "nyc": "America/New_York", "los angeles": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles", "chicago": "America/Chicago", "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo",
    "dubai": "Asia/Dubai", "singapore": "Asia/Singapore", "sydney": "Australia/Sydney", "india": "Asia/Kolkata",
    "chennai": "Asia/Kolkata", "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "bangalore": "Asia/Kolkata",
    "beijing": "Asia/Shanghai", "china": "Asia/Shanghai", "hong kong": "Asia/Hong_Kong", "moscow": "Europe/Moscow",
    "toronto": "America/Toronto", "canada": "America/Toronto", "usa": "America/New_York", "germany": "Europe/Berlin",
    "france": "Europe/Paris", "seoul": "Asia/Seoul", "korea": "Asia/Seoul", "kuala lumpur": "Asia/Kuala_Lumpur",
    "malaysia": "Asia/Kuala_Lumpur", "riyadh": "Asia/Riyadh", "saudi": "Asia/Riyadh", "cairo": "Africa/Cairo",
}
_TZ_RE = "|".join(sorted((re.escape(k) for k in _TZ), key=len, reverse=True))
_HOLIDAYS = {"christmas": (12, 25), "new year": (1, 1), "new year's": (1, 1), "new years": (1, 1),
             "halloween": (10, 31), "valentine's day": (2, 14), "valentines day": (2, 14), "independence day": (8, 15)}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                        "september", "october", "november", "december"], 1)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})


def _target_date(spec: str, today: date) -> Optional[date]:
    spec = spec.strip().lower().rstrip("?. ")
    if spec in _HOLIDAYS:
        mo, d = _HOLIDAYS[spec]
        out = date(today.year, mo, d)
        return out if out >= today else date(today.year + 1, mo, d)
    if spec in _WEEKDAYS:
        delta = (_WEEKDAYS.index(spec) - today.weekday()) % 7 or 7
        return today + timedelta(days=delta)
    m = re.fullmatch(r"(?P<m>[a-z]+)\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<y>\d{4}))?|(?P<d2>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<m2>[a-z]+)(?:,?\s+(?P<y2>\d{4}))?", spec)
    if m:
        mon = _MONTHS.get((m.group("m") or m.group("m2") or "")[:9]) or _MONTHS.get((m.group("m") or m.group("m2") or "")[:3])
        day = int(m.group("d") or m.group("d2"))
        year = m.group("y") or m.group("y2")
        if mon:
            try:
                out = date(int(year) if year else today.year, mon, day)
            except ValueError:
                return None
            if not year and out < today:
                out = date(today.year + 1, mon, day)
            return out
    return None


def date_answer(text: str, now: Optional[datetime] = None) -> Optional[str]:
    now = now or datetime.now()
    today = now.date()
    t = re.sub(r"\s+", " ", text.strip().lower().rstrip("?.! "))
    m = re.match(r"^(?:how many|how long)\s+(?:days|sleeps)\s+(?:until|till|to|before)\s+(?P<x>.+)$", t) \
        or re.match(r"^(?:days|how long)\s+(?:until|till|to)\s+(?P<x>.+)$", t)
    if m:
        target = _target_date(m.group("x"), today)
        if target:
            n = (target - today).days
            return f"{n} day{'s' if n != 1 else ''} until {m.group('x').strip().title()} ({target.strftime('%A, %d %B %Y')})."
    m = re.match(r"^what(?:'s| is| will be)?\s+(?:the\s+)?(?:date|day)\s+(?:will it be\s+|is it\s+|would it be\s+)?(?P<dir>in|after)\s+(?P<n>\d+)\s+(?P<u>days?|weeks?|months?)(?:\s+from (?:now|today))?$", t) \
        or re.match(r"^(?:what(?:'s| is)\s+)?(?P<n>\d+)\s+(?P<u>days?|weeks?)\s+from\s+(?:now|today)$", t)
    if m:
        n = int(m.group("n"))
        unit = m.group("u")
        target = today + (timedelta(days=n) if unit.startswith("day") else timedelta(weeks=n) if unit.startswith("week") else timedelta(days=30 * n))
        return f"{n} {unit} from today is {target.strftime('%A, %d %B %Y')}."
    m = re.match(r"^what day (?:of the week )?(?:is|was|will be|falls on)\s+(?P<x>.+)$", t)
    if m and m.group("x") not in ("it", "it today", "today"):
        target = _target_date(m.group("x"), today)
        if target:
            return f"{target.strftime('%d %B %Y')} is a {target.strftime('%A')}."
    m = re.match(rf"^(?:what(?:'s| is)\s+)?(?:the\s+)?(?:current\s+)?time\s+(?:is it\s+)?(?:now\s+)?in\s+(?P<c>{_TZ_RE})(?:\s+(?:right\s+)?now)?$", t) \
        or re.match(rf"^what time is it in\s+(?P<c>{_TZ_RE})(?:\s+(?:right\s+)?now)?$", t)
    if m:
        try:
            from zoneinfo import ZoneInfo
            zone = ZoneInfo(_TZ[m.group("c")])
        except Exception:
            return None
        local = datetime.now(zone)
        return f"It's {local.strftime('%I:%M %p').lstrip('0')} on {local.strftime('%A')} in {m.group('c').title()}."
    m = re.match(r"^(?:is|was|will)\s+(?P<y>\d{4})\s+(?:be\s+)?a\s+leap\s+year$", t)
    if m:
        y = int(m.group("y"))
        leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        return f"Yes, {y} is a leap year." if leap else f"No, {y} is not a leap year."
    m = re.match(r"^how old (?:is (?:someone|a person|somebody) born|would i be if i was born|am i if i was born)\s+in\s+(?P<y>\d{4})$", t)
    if m:
        age = today.year - int(m.group("y"))
        return f"About {age} years old (born in {m.group('y')})."
    return None


def chance_answer(text: str, rng: Optional[random.Random] = None) -> Optional[str]:
    rng = rng or random.SystemRandom()
    t = re.sub(r"\s+", " ", text.strip().lower().rstrip("?.! "))
    if re.fullmatch(r"(?:flip|toss) (?:a |the )?coin|heads or tails", t):
        return f"It's {rng.choice(['heads', 'tails'])}."
    m = re.fullmatch(r"(?:roll|throw) (?:a |the |(?P<n>\d|two|three) )?(?:d(?P<s>\d+)|dice|die|dices)", t)
    if m:
        count = {"two": 2, "three": 3}.get(m.group("n") or "", int(m.group("n")) if (m.group("n") or "").isdigit() else 1)
        sides = int(m.group("s") or 6)
        rolls = [rng.randint(1, sides) for _ in range(max(1, min(count, 10)))]
        return f"You rolled {', '.join(map(str, rolls))}." + (f" Total {sum(rolls)}." if len(rolls) > 1 else "")
    m = re.fullmatch(r"(?:pick|give me|choose|generate) a random number(?: between| from)? (?P<a>-?\d+) (?:and|to) (?P<b>-?\d+)", t)
    if m:
        a, b = sorted((int(m.group("a")), int(m.group("b"))))
        return f"{rng.randint(a, b)}."
    return None


def quick_answer(text: str, now: Optional[datetime] = None) -> Optional[str]:
    """Instant deterministic answer for math, units, dates, world time and chance, or None."""
    if not text or len(text) > 160:
        return None
    t = text.strip()
    for fn in (convert_units, date_answer, chance_answer):
        try:
            out = fn(t) if fn is not date_answer else fn(t, now)
        except Exception:
            out = None
        if out:
            return out
    low = re.sub(r"\s+", " ", t.lower().rstrip("?.! "))
    low = re.sub(r"^(?:what(?:'s| is)|whats|calculate|how much is)\s+", "", low)
    m = _TIP.match(low)
    if m:
        p, n = float(m.group("p")), float(m.group("n"))
        tip = round(p * n / 100, 2)
        return f"A {fmt_number(p)}% tip on {fmt_number(n)} is {fmt_number(tip)}, so {fmt_number(round(n + tip, 2))} in total."
    m = _PERCENT.match(low)
    if m:
        p, n = float(m.group("p")), float(m.group("n"))
        return f"{fmt_number(p)}% of {fmt_number(n)} is {fmt_number(round(p * n / 100, 4))}."
    m = re.fullmatch(r"(?P<a>\d+(?:\.\d+)?) is what (?:percent|percentage|%) of (?P<b>\d+(?:\.\d+)?)", low)
    if m and float(m.group("b")):
        return f"{fmt_number(float(m.group('a')))} is {fmt_number(round(100 * float(m.group('a')) / float(m.group('b')), 2))}% of {fmt_number(float(m.group('b')))}."
    expr = _math_expression(t)
    if expr:
        try:
            value = safe_eval(expr)
        except ZeroDivisionError:
            return "That's a division by zero, so there's no answer."
        except Exception:
            return None
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return f"That's {fmt_number(round(value, 10) if isinstance(value, float) else value)}."
    return None


class QuickAnswerInput(Contract):
    query: str = Field(min_length=1, max_length=300, description="Math, unit conversion, date or world-time question")


class MessageOutput(Contract):
    message: str
    data: dict = Field(default_factory=dict)


class QuickAnswerTool(Tool):
    definition = ToolDefinition(
        name="quick_answer",
        description="Instantly answers calculations, percentages, unit and temperature conversions, date maths "
                    "(days until, what day is), world clock, coin flips, dice and random numbers - offline.",
        input_model=QuickAnswerInput, output_model=MessageOutput, read_only=True, risk=RiskLevel.READ_ONLY,
        timeout_s=2.0, tags=("calculator", "math", "convert", "units", "date", "time zone"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        query = arguments["query"] if isinstance(arguments, dict) else arguments.query
        answer = quick_answer(query)
        if answer is None:
            raise ValueError("I can't calculate that one offline.")
        return {"message": answer, "data": {"query": query}}


# ============================================================================ battery / network

class EmptyInput(Contract):
    pass


class BatteryStatusTool(Tool):
    definition = ToolDefinition(
        name="battery_status", description="Reports laptop battery percentage, whether it is charging and the time left.",
        input_model=EmptyInput, output_model=MessageOutput, read_only=True, risk=RiskLevel.READ_ONLY, timeout_s=3.0,
        tags=("battery", "power", "charging", "system"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return {"message": "This PC has no battery, it's running on mains power.", "data": {"present": False}}
        pct = round(b.percent)
        if b.power_plugged:
            msg = f"Battery is at {pct}% and charging." if pct < 100 else "Battery is full and plugged in."
        else:
            left = b.secsleft
            if left and left > 0 and left != psutil.POWER_TIME_UNLIMITED:
                h, m = divmod(int(left) // 60, 60)
                span = f"{h} hour{'s' if h != 1 else ''} {m} minutes" if h else f"{m} minutes"
                msg = f"Battery is at {pct}%, about {span} left."
            else:
                msg = f"Battery is at {pct}%."
            if pct <= 20:
                msg += " You should plug in the charger soon."
        return {"message": msg, "data": {"present": True, "percent": pct, "plugged": bool(b.power_plugged)}}


def _local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent for UDP connect
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _wifi_name() -> str:
    if sys.platform != "win32":
        return ""
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=3,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        m = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.M)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""


def _online(timeout: float = 1.5) -> bool:
    for host in (("1.1.1.1", 53), ("8.8.8.8", 53)):
        try:
            with socket.create_connection(host, timeout=timeout):
                return True
        except OSError:
            continue
    return False


class NetworkInfoTool(Tool):
    definition = ToolDefinition(
        name="network_info", description="Shows this PC's IP address, the Wi-Fi network it is on and whether the internet is reachable.",
        input_model=EmptyInput, output_model=MessageOutput, read_only=True, risk=RiskLevel.READ_ONLY, timeout_s=6.0,
        tags=("network", "wifi", "ip address", "internet", "system"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        ip, wifi, online = _local_ip(), _wifi_name(), _online()
        parts = [f"You're {'online' if online else 'offline - the internet is not reachable'}."]
        if wifi:
            parts.append(f"Connected to Wi-Fi {wifi}.")
        parts.append(f"Your local IP address is {ip}.")
        return {"message": " ".join(parts), "data": {"ip": ip, "wifi": wifi, "online": online, "host": socket.gethostname()}}


# ============================================================================ stopwatch

class StopwatchInput(Contract):
    action: str = Field(default="start", description="start, lap, stop, reset or status")


def _fmt_span(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} hour{'s' if h != 1 else ''} {m} minute{'s' if m != 1 else ''}"
    if m:
        return f"{m} minute{'s' if m != 1 else ''} {s} second{'s' if s != 1 else ''}"
    return f"{seconds:.1f} seconds"


class StopwatchTool(Tool):
    definition = ToolDefinition(
        name="stopwatch", description="Starts, laps, stops or resets a stopwatch and reports the elapsed time.",
        input_model=StopwatchInput, output_model=MessageOutput, read_only=False, risk=RiskLevel.REVERSIBLE, timeout_s=2.0,
        tags=("stopwatch", "timer", "time"), execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.started: Optional[float] = None
        self.accumulated = 0.0
        self.laps: list[float] = []

    def elapsed(self) -> float:
        return self.accumulated + ((self.clock() - self.started) if self.started is not None else 0.0)

    def run(self, arguments: Any) -> dict[str, Any]:
        action = (arguments["action"] if isinstance(arguments, dict) else arguments.action).lower().strip()
        if action in ("start", "resume", "begin"):
            if self.started is not None:
                return {"message": f"The stopwatch is already running: {_fmt_span(self.elapsed())}.", "data": {}}
            self.started = self.clock()
            return {"message": "Stopwatch started." if not self.accumulated else "Stopwatch resumed.", "data": {}}
        if action == "lap":
            self.laps.append(self.elapsed())
            return {"message": f"Lap {len(self.laps)}: {_fmt_span(self.laps[-1])}.", "data": {"laps": self.laps}}
        if action in ("stop", "pause", "end"):
            total = self.elapsed()
            if self.started is not None:
                self.accumulated, self.started = total, None
            return {"message": f"Stopwatch stopped at {_fmt_span(total)}.", "data": {"seconds": round(total, 2)}}
        if action in ("reset", "clear"):
            self.started, self.accumulated, self.laps = None, 0.0, []
            return {"message": "Stopwatch reset.", "data": {}}
        state = "running" if self.started is not None else "stopped"
        return {"message": f"The stopwatch is {state} at {_fmt_span(self.elapsed())}.", "data": {"seconds": round(self.elapsed(), 2)}}


# ============================================================================ SQLite-backed personal data

_SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL, done_at REAL);
CREATE TABLE IF NOT EXISTS memory_facts (id INTEGER PRIMARY KEY AUTOINCREMENT, fact TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS shortcuts (phrase TEXT PRIMARY KEY, steps TEXT NOT NULL, created_at REAL NOT NULL);
"""


def default_db_path() -> Path:
    try:
        from jarvis.config import load
        return ROOT / load().paths.db
    except Exception:
        return ROOT / "db" / "jarvis.db"


class PersonalStore:
    """Small, synchronous SQLite store (WAL) shared with the rest of JARVIS's database."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self._lock = threading.Lock()
        self._ready = False

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=5)
        con.execute("PRAGMA busy_timeout=5000")
        if not self._ready:
            con.executescript(_SCHEMA)
            self._ready = True
        return con

    # -- todos
    def add_todo(self, text: str) -> int:
        with self._lock, self.connect() as con:
            return int(con.execute("INSERT INTO todos(text, created_at) VALUES (?, ?)", (text, time.time())).lastrowid)

    def todos(self, include_done: bool = False) -> list[tuple[int, str, bool]]:
        with self._lock, self.connect() as con:
            q = "SELECT id, text, done FROM todos" + ("" if include_done else " WHERE done = 0") + " ORDER BY id"
            return [(r[0], r[1], bool(r[2])) for r in con.execute(q)]

    def complete_todo(self, which: str) -> Optional[str]:
        return self._pick_todo(which, "UPDATE todos SET done = 1, done_at = ? WHERE id = ?", with_time=True)

    def remove_todo(self, which: str) -> Optional[str]:
        return self._pick_todo(which, "DELETE FROM todos WHERE id = ?")

    def _pick_todo(self, which: str, sql: str, with_time: bool = False) -> Optional[str]:
        items = self.todos()
        target = None
        w = which.strip().lower()
        ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": len(items)}
        m = re.fullmatch(r"(?:number\s+|#)?(\d+)", w)
        if m and 1 <= int(m.group(1)) <= len(items):
            target = items[int(m.group(1)) - 1]
        elif w in ordinals and items and 1 <= ordinals[w] <= len(items):
            target = items[ordinals[w] - 1]
        else:
            matches = [it for it in items if w and w in it[1].lower()]
            target = matches[0] if matches else None
        if target is None:
            return None
        with self._lock, self.connect() as con:
            con.execute(sql, (time.time(), target[0]) if with_time else (target[0],))
        return target[1]

    def clear_done(self) -> int:
        with self._lock, self.connect() as con:
            return con.execute("DELETE FROM todos WHERE done = 1").rowcount

    # -- facts
    def add_fact(self, fact: str) -> int:
        with self._lock, self.connect() as con:
            return int(con.execute("INSERT INTO memory_facts(fact, created_at) VALUES (?, ?)", (fact, time.time())).lastrowid)

    def facts(self, query: str = "", limit: int = 5) -> list[tuple[int, str]]:
        with self._lock, self.connect() as con:
            rows = [(r[0], r[1]) for r in con.execute("SELECT id, fact FROM memory_facts ORDER BY id DESC")]
        if not query:
            return rows[:limit]
        words = {_stem(w) for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2 and w not in _STOP}
        scored = [(len(words & {_stem(w) for w in re.findall(r"[a-z0-9]+", f.lower())}), i, f) for i, f in rows]
        return [(i, f) for s, i, f in sorted(scored, key=lambda x: (-x[0], -x[1])) if s > 0][:limit]

    def forget_fact(self, query: str) -> Optional[str]:
        hits = self.facts(query, limit=1)
        if not hits:
            return None
        with self._lock, self.connect() as con:
            con.execute("DELETE FROM memory_facts WHERE id = ?", (hits[0][0],))
        return hits[0][1]

    # -- shortcuts
    def save_shortcut(self, phrase: str, steps: list[str]) -> None:
        with self._lock, self.connect() as con:
            con.execute("INSERT OR REPLACE INTO shortcuts(phrase, steps, created_at) VALUES (?, ?, ?)",
                        (normalize_phrase(phrase), json.dumps(steps), time.time()))
        _shortcut_cache.clear()

    def shortcuts(self) -> dict[str, list[str]]:
        if "all" not in _shortcut_cache:
            with self._lock, self.connect() as con:
                _shortcut_cache["all"] = {p: json.loads(s) for p, s in con.execute("SELECT phrase, steps FROM shortcuts ORDER BY phrase")}
        return dict(_shortcut_cache["all"])

    def delete_shortcut(self, phrase: str) -> bool:
        with self._lock, self.connect() as con:
            n = con.execute("DELETE FROM shortcuts WHERE phrase = ?", (normalize_phrase(phrase),)).rowcount
        _shortcut_cache.clear()
        return bool(n)

    # -- history
    def recent_requests(self, limit: int = 10) -> list[str]:
        try:
            with self._lock, self.connect() as con:
                rows = con.execute("SELECT payload FROM requests ORDER BY rowid DESC LIMIT ?", (limit * 3,)).fetchall()
        except sqlite3.Error:
            return []
        out: list[str] = []
        for (payload,) in rows:
            try:
                text = json.loads(payload).get("text", "")
            except Exception:
                continue
            if text and not re.match(r"^(?:what did i (?:ask|say)|show (?:my )?(?:command )?history|repeat|again|do (?:it|that) again)", text.lower()):
                out.append(text)
            if len(out) >= limit:
                break
        return out


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


_STOP = {"the", "and", "for", "what", "who", "when", "where", "which", "about", "does", "did", "you", "your", "remember", "know", "tell"}
_shortcut_cache: dict[str, dict[str, list[str]]] = {}
_store: Optional[PersonalStore] = None


def get_store() -> PersonalStore:
    global _store
    if _store is None:
        _store = PersonalStore()
    return _store


def set_store(store: Optional[PersonalStore]) -> None:
    global _store
    _store = store
    _shortcut_cache.clear()


def normalize_phrase(text: str) -> str:
    t = re.sub(r"[^\w\s']", " ", (text or "").lower())
    t = re.sub(r"^(?:hey jarvis|ok jarvis|jarvis|please)\s+", "", re.sub(r"\s+", " ", t).strip())
    return t.strip()


# ---------------------------------------------------------------- todo tool

class TodoInput(Contract):
    action: str = Field(default="list", description="add, list, done, remove or clear_done")
    item: str = Field(default="", max_length=500, description="The task text, or which task (number, first/last, or words)")


class TodoTool(Tool):
    definition = ToolDefinition(
        name="todo", description="Manages your to-do list (stored locally): add a task, list tasks, mark one done, remove one.",
        input_model=TodoInput, output_model=MessageOutput, read_only=False, risk=RiskLevel.REVERSIBLE, timeout_s=5.0,
        tags=("todo", "task list", "checklist", "productivity"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = TodoInput(**arguments)
        store, action, item = get_store(), arguments.action.lower().strip(), arguments.item.strip().strip(".")
        if action == "add":
            if not item:
                raise ValueError("What should I add to your to-do list?")
            store.add_todo(item)
            n = len(store.todos())
            return {"message": f"Added '{item}' to your to-do list. You have {n} open task{'s' if n != 1 else ''}.", "data": {"count": n}}
        if action in ("done", "complete", "finish", "check"):
            text = store.complete_todo(item)
            return {"message": f"Marked '{text}' as done." if text else "I couldn't find that task on your list.", "data": {}}
        if action in ("remove", "delete"):
            text = store.remove_todo(item)
            return {"message": f"Removed '{text}' from your list." if text else "I couldn't find that task on your list.", "data": {}}
        if action in ("clear_done", "clear"):
            n = store.clear_done()
            return {"message": f"Cleared {n} finished task{'s' if n != 1 else ''}.", "data": {"removed": n}}
        items = store.todos()
        if not items:
            return {"message": "Your to-do list is empty.", "data": {"items": []}}
        listed = "; ".join(f"{i}. {t}" for i, (_, t, _) in enumerate(items[:7], 1))
        more = f" and {len(items) - 7} more" if len(items) > 7 else ""
        return {"message": f"You have {len(items)} task{'s' if len(items) != 1 else ''}: {listed}{more}.",
                "data": {"items": [t for _, t, _ in items]}}


# ---------------------------------------------------------------- personal memory (SQLite + RAG)

class FactInput(Contract):
    fact: str = Field(min_length=1, max_length=1000, description="The fact to remember, e.g. 'my car is parked on level 2'")


class QueryInput(Contract):
    query: str = Field(default="", max_length=500, description="What to recall; empty = recent facts")


_SECRET = re.compile(r"\b(?:password|passcode|pin|otp|cvv|card number|api key|secret key|private key)\b", re.I)


class RememberFactTool(Tool):
    definition = ToolDefinition(
        name="remember_fact", description="Remembers a personal fact for later (stored locally and added to the knowledge base), e.g. 'remember that my car is on level 2'.",
        input_model=FactInput, output_model=MessageOutput, read_only=False, risk=RiskLevel.REVERSIBLE, timeout_s=10.0,
        tags=("memory", "remember", "personal", "rag"), execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, knowledge_service: Any = None) -> None:
        self.knowledge_service = knowledge_service

    def run(self, arguments: Any) -> dict[str, Any]:
        fact = (arguments["fact"] if isinstance(arguments, dict) else arguments.fact).strip().rstrip(".")
        fact = re.sub(r"^(?:that|this)\s+", "", fact)
        if _SECRET.search(fact):
            return {"message": "I won't store passwords, PINs or keys in memory. Please use a password manager for those.", "data": {"stored": False}}
        store = get_store()
        store.add_fact(fact)
        self._index(store)
        return {"message": f"Got it, I'll remember that {fact}.", "data": {"stored": True}}

    def _index(self, store: PersonalStore) -> None:
        """Mirror all facts into the RAG knowledge base as one document so grounded chat can cite them."""
        engine = getattr(self.knowledge_service, "knowledge_engine", None)
        if engine is None:
            return
        try:
            facts = [f for _, f in store.facts(limit=10_000)]
            col = engine.get_or_create_collection("Personal Memory")
            engine.index_document_text(col.collection_id, "memory://personal-facts",
                                       "# Things the user asked JARVIS to remember\n\n" + "\n".join(f"- {f}" for f in reversed(facts)),
                                       privacy_scope="scope:memory")
        except Exception as exc:
            logger.debug("Could not index personal facts: %s", exc)


class RecallFactsTool(Tool):
    definition = ToolDefinition(
        name="recall_facts", description="Recalls personal facts you asked JARVIS to remember (e.g. 'where did I park', 'what do you remember about my car').",
        input_model=QueryInput, output_model=MessageOutput, read_only=True, risk=RiskLevel.READ_ONLY, timeout_s=5.0,
        tags=("memory", "recall", "personal"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        query = arguments["query"] if isinstance(arguments, dict) else arguments.query
        hits = get_store().facts(query, limit=3)
        if not hits:
            return {"message": "I don't have anything remembered about that." if query else "You haven't asked me to remember anything yet.", "data": {}}
        if len(hits) == 1:
            return {"message": f"You told me {hits[0][1]}.", "data": {"facts": [hits[0][1]]}}
        return {"message": "Here's what I remember: " + "; ".join(f for _, f in hits) + ".", "data": {"facts": [f for _, f in hits]}}


class ForgetFactTool(RememberFactTool):
    definition = ToolDefinition(
        name="forget_fact", description="Forgets a remembered personal fact.",
        input_model=QueryInput, output_model=MessageOutput, read_only=False, risk=RiskLevel.REVERSIBLE, timeout_s=10.0,
        tags=("memory", "forget", "personal"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        query = arguments["query"] if isinstance(arguments, dict) else arguments.query
        store = get_store()
        fact = store.forget_fact(query)
        if fact is None:
            return {"message": "I couldn't find that in my memory.", "data": {}}
        self._index(store)
        return {"message": f"Okay, I've forgotten that {fact}.", "data": {}}


# ---------------------------------------------------------------- shortcuts (voice macros)

class ShortcutInput(Contract):
    phrase: str = Field(min_length=1, max_length=120, description="What you will say, e.g. 'goodnight'")
    steps: list[str] = Field(default_factory=list, description="Commands to run in order, e.g. ['lock the pc', 'mute']")


class ShortcutNameInput(Contract):
    phrase: str = Field(default="", max_length=120)


_STEP_VERBS = ("open|close|lock|mute|unmute|play|pause|start|set|turn|launch|show|send|search|remind|take|minimi[sz]e|"
               "maximi[sz]e|go|stop|read|check|put|switch|sleep|volume|dim|increase|decrease|resume|find|tell|message|text|"
               "run|create|say|restart|shut|empty|snap|arrange|join|call|dial|flip|roll|add|mark|remember|generate|"
               "enable|disable|mute|brighten|lower|raise|download|copy|move|delete|rename|organi[sz]e|clean|note|save|record")


def split_steps(text: str) -> list[str]:
    parts = re.split(rf"\s*(?:,\s*(?:and\s+)?(?:then\s+)?|\s+and then\s+|\s+then\s+|\s+and\s+(?=(?:{_STEP_VERBS})(?:s|es)?\b)|;)\s*",
                     text.strip(), flags=re.I)
    steps = []
    for p in parts:
        p = p.strip(" .")
        if not p:
            continue
        # "opens notion" / "plays music" (as in "a shortcut that opens ...") -> imperative
        m = re.match(rf"^(?P<v>{_STEP_VERBS})(?:es|s)\b(?P<rest>.*)$", p, re.I)
        if m:
            p = m.group("v") + m.group("rest")
        steps.append(p)
    return steps


_RESERVED = {"yes", "no", "stop", "cancel", "confirm", "again", "repeat", "help"}


class CreateShortcutTool(Tool):
    definition = ToolDefinition(
        name="create_shortcut", description="Creates a voice shortcut that runs several commands, e.g. 'when I say goodnight, lock the pc and mute the volume'.",
        input_model=ShortcutInput, output_model=MessageOutput, read_only=False, risk=RiskLevel.REVERSIBLE, timeout_s=5.0,
        tags=("shortcut", "macro", "routine", "automation"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = ShortcutInput(**arguments)
        phrase = normalize_phrase(arguments.phrase)
        steps = [s for step in arguments.steps for s in split_steps(step)]
        if not phrase or phrase in _RESERVED:
            raise ValueError("Please pick a different phrase for the shortcut.")
        if not steps:
            raise ValueError("What should the shortcut do?")
        if len(steps) > 8:
            raise ValueError("A shortcut can have at most 8 steps.")
        get_store().save_shortcut(phrase, steps)
        return {"message": f"Done. When you say '{phrase}', I'll " + ", then ".join(steps) + ".", "data": {"phrase": phrase, "steps": steps}}


class ListShortcutsTool(Tool):
    definition = ToolDefinition(
        name="list_shortcuts", description="Lists your voice shortcuts.", input_model=ShortcutNameInput, output_model=MessageOutput,
        read_only=True, risk=RiskLevel.READ_ONLY, timeout_s=3.0, tags=("shortcut", "macro", "routine"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        items = get_store().shortcuts()
        if not items:
            return {"message": "You have no shortcuts yet. Try: when I say goodnight, lock the PC and mute.", "data": {}}
        listed = "; ".join(f"'{p}' runs {', '.join(s)}" for p, s in items.items())
        return {"message": f"You have {len(items)} shortcut{'s' if len(items) != 1 else ''}: {listed}.", "data": {"shortcuts": items}}


class DeleteShortcutTool(Tool):
    definition = ToolDefinition(
        name="delete_shortcut", description="Deletes a voice shortcut.", input_model=ShortcutNameInput, output_model=MessageOutput,
        read_only=False, risk=RiskLevel.REVERSIBLE, timeout_s=3.0, tags=("shortcut", "macro"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        phrase = arguments["phrase"] if isinstance(arguments, dict) else arguments.phrase
        ok = get_store().delete_shortcut(phrase)
        return {"message": f"Deleted the '{normalize_phrase(phrase)}' shortcut." if ok else "I couldn't find that shortcut.", "data": {}}


# ---------------------------------------------------------------- history, password, recycle bin

class HistoryInput(Contract):
    limit: int = Field(default=5, ge=1, le=20)


class CommandHistoryTool(Tool):
    definition = ToolDefinition(
        name="command_history", description="Tells you the last things you asked JARVIS.", input_model=HistoryInput, output_model=MessageOutput,
        read_only=True, risk=RiskLevel.READ_ONLY, timeout_s=3.0, tags=("history", "recent commands"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        limit = arguments["limit"] if isinstance(arguments, dict) else arguments.limit
        items = get_store().recent_requests(limit)
        if not items:
            return {"message": "I don't have any earlier commands yet.", "data": {}}
        return {"message": "Recently you asked: " + "; ".join(f"'{t}'" for t in items) + ".", "data": {"history": items}}


class PasswordInput(Contract):
    length: int = Field(default=16, ge=8, le=64)
    symbols: bool = True


def make_password(length: int = 16, symbols: bool = True) -> str:
    pools = [string.ascii_lowercase, string.ascii_uppercase, string.digits] + (["!@#$%^&*-_=+?"] if symbols else [])
    chars = [secrets.choice(p) for p in pools]
    alphabet = "".join(pools)
    chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "win32":
            proc = subprocess.run(["clip"], input=text.encode("utf-16-le"), timeout=3,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return proc.returncode == 0
        for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["pbcopy"]):
            try:
                if subprocess.run(cmd, input=text.encode(), timeout=3).returncode == 0:
                    return True
            except (OSError, subprocess.SubprocessError):
                continue
    except Exception:
        pass
    return False


class GeneratePasswordTool(Tool):
    definition = ToolDefinition(
        name="generate_password", description="Generates a strong random password and copies it to the clipboard (it is never spoken or saved).",
        input_model=PasswordInput, output_model=MessageOutput, read_only=True, risk=RiskLevel.READ_ONLY, timeout_s=5.0,
        tags=("password", "security", "generator"), execution_method=ExecutionMethod.NATIVE,
    )

    def __init__(self, clipboard: Callable[[str], bool] = copy_to_clipboard) -> None:
        self.clipboard = clipboard

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = PasswordInput(**arguments)
        pw = make_password(arguments.length, arguments.symbols)
        if not self.clipboard(pw):
            raise RuntimeError("I couldn't reach the clipboard, so I didn't create a password.")
        return {"message": f"I generated a {arguments.length}-character password and copied it to your clipboard. Paste it where you need it.",
                "data": {"length": arguments.length}}


class EmptyRecycleBinTool(Tool):
    definition = ToolDefinition(
        name="empty_recycle_bin", description="Permanently empties the Windows Recycle Bin (asks for confirmation first).",
        input_model=EmptyInput, output_model=MessageOutput, read_only=False, risk=RiskLevel.DESTRUCTIVE, timeout_s=60.0,
        tags=("recycle bin", "trash", "cleanup", "disk space"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if sys.platform != "win32":
            raise RuntimeError("Emptying the Recycle Bin is only available on Windows.")
        import ctypes
        flags = 0x1 | 0x2 | 0x4  # no confirmation dialog, no progress UI, no sound (JARVIS already confirmed)
        result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        if result not in (0, -2147418113):  # S_OK, or E_UNEXPECTED when the bin is already empty
            raise RuntimeError(f"Windows could not empty the Recycle Bin (code {result}).")
        return {"message": "The Recycle Bin is empty.", "data": {}}


def create_everyday_tools() -> list[Tool]:
    return [QuickAnswerTool(), BatteryStatusTool(), NetworkInfoTool(), StopwatchTool(), TodoTool(), RememberFactTool(),
            RecallFactsTool(), ForgetFactTool(), CreateShortcutTool(), ListShortcutsTool(), DeleteShortcutTool(),
            CommandHistoryTool(), GeneratePasswordTool(), EmptyRecycleBinTool()]
