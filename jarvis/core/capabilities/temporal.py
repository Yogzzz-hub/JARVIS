"""Canonical Temporal Resolver for JARVIS Edge.

Provides deterministic parsing and normalization of relative/absolute dates,
times, and date/time ranges using the local timezone and reference datetime.
Output typed structures:
- DatePoint
- DateRange
- DateTimePoint
- DateTimeRange
- TimeRange
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Optional, Tuple, Union


@dataclass(frozen=True)
class DatePoint:
    """A concrete resolved calendar date."""
    resolved_date: date
    label: str = ""

    @property
    def isoformat(self) -> str:
        return self.resolved_date.isoformat()

    def __str__(self) -> str:
        return self.label or self.isoformat


@dataclass(frozen=True)
class DateRange:
    """A bounded date interval [start_date, end_date]."""
    start_date: date
    end_date: date
    label: str = ""

    @property
    def start_iso(self) -> str:
        return self.start_date.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end_date.isoformat()

    def contains(self, d: date) -> bool:
        return self.start_date <= d <= self.end_date

    def __str__(self) -> str:
        return self.label or f"{self.start_iso} to {self.end_iso}"


@dataclass(frozen=True)
class TimeRange:
    """A bounded local time interval [start_time, end_time]."""
    start_time: time
    end_time: time
    label: str = ""

    def __str__(self) -> str:
        return self.label or f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


@dataclass(frozen=True)
class DateTimePoint:
    """A concrete resolved timestamp with date and time."""
    resolved_dt: datetime
    label: str = ""

    @property
    def isoformat(self) -> str:
        return self.resolved_dt.isoformat()

    def __str__(self) -> str:
        return self.label or self.isoformat


@dataclass(frozen=True)
class DateTimeRange:
    """A bounded datetime interval [start_dt, end_dt]."""
    start_dt: datetime
    end_dt: datetime
    label: str = ""

    @property
    def start_iso(self) -> str:
        return self.start_dt.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end_dt.isoformat()

    def contains(self, dt: datetime) -> bool:
        return self.start_dt <= dt <= self.end_dt

    def __str__(self) -> str:
        return self.label or f"{self.start_iso} to {self.end_iso}"


# Type alias for any resolved temporal value
TemporalConstraint = Union[DatePoint, DateRange, DateTimePoint, DateTimeRange, TimeRange]

DAYS_OF_WEEK = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

ORDINAL_WEEKS = {
    "first": 1, "1st": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
    "last": 5, "final": 5,
}


class TemporalResolver:
    """Canonical resolver translating natural language temporal expressions into typed constraints."""

    def __init__(self, reference_dt: Optional[datetime] = None):
        if reference_dt is None:
            # Default to local current time
            self._ref = datetime.now().astimezone()
        else:
            self._ref = reference_dt

    @property
    def today(self) -> date:
        return self._ref.date()

    @property
    def reference_datetime(self) -> datetime:
        return self._ref

    def resolve(self, text: str) -> Tuple[Optional[TemporalConstraint], str]:
        """Resolves temporal expressions from text.

        Returns:
            (resolved_constraint, text_with_temporal_expression_removed)
        """
        lowered = text.casefold().strip()

        # 1. Check time range with relative/named date:
        # e.g., "from last Tuesday between 2 and 6 PM"
        res, remaining = self._match_combined_date_and_time(lowered, text)
        if res:
            return res, remaining

        # 2. Check standalone time ranges:
        # e.g., "between 2 and 6 PM", "from 10 AM to 4 PM", "until 10:30 tonight"
        res, remaining = self._match_time_range(lowered, text)
        if res:
            return res, remaining

        # 3. Check week intervals in named months:
        # e.g., "second week of September", "first week of August"
        res, remaining = self._match_week_of_month(lowered, text)
        if res:
            return res, remaining

        # 4. Check bounded date ranges:
        # e.g., "after Monday but before yesterday", "between Tuesday and Thursday",
        # "from Monday morning to Wednesday evening", "since Monday"
        res, remaining = self._match_bounded_date_range(lowered, text)
        if res:
            return res, remaining

        # 5. Check relative intervals:
        # e.g., "past 3 days", "last 7 days", "last weekend", "earlier this month"
        res, remaining = self._match_relative_interval(lowered, text)
        if res:
            return res, remaining

        # 6. Check single relative dates:
        # e.g., "yesterday", "today", "tomorrow", "last Tuesday", "Monday", "last Friday"
        res, remaining = self._match_single_relative_date(lowered, text)
        if res:
            return res, remaining

        return None, text

    def _clean_span(self, original_text: str, start: int, end: int) -> str:
        """Removes the matched span and cleans up dangling prepositions/whitespace."""
        before = original_text[:start].rstrip(" ,;")
        after = original_text[end:].lstrip(" ,;")
        # Remove dangling "from", "on", "during", "at", "between", "for", "in" at the end of `before`
        before = re.sub(r"\b(?:from|on|during|at|between|for|in|created|modified|saved)\s*$", "", before, flags=re.I).strip()
        cleaned = f"{before} {after}".strip()
        return re.sub(r"\s+", " ", cleaned)

    def _match_combined_date_and_time(self, lowered: str, original: str) -> Tuple[Optional[TemporalConstraint], str]:
        # "from last Tuesday between 2 and 6 PM"
        # "yesterday between 10 AM and 1 PM"
        pat = re.compile(
            r"\b(?:from\s+)?(?P<date_expr>(?:last|past|this)?\s*(?:yesterday|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\s+"
            r"(?:between\s+(?P<t1>\d{1,2}(?::\d{2})?)\s*(?P<p1>am|pm)?\s*(?:and|to|-)\s*(?P<t2>\d{1,2}(?::\d{2})?)\s*(?P<p2>am|pm)|"
            r"from\s+(?P<t3>\d{1,2}(?::\d{2})?)\s*(?P<p3>am|pm)?\s*(?:to|-)\s*(?P<t4>\d{1,2}(?::\d{2})?)\s*(?P<p4>am|pm))\b",
            re.I,
        )
        m = pat.search(lowered)
        if not m:
            return None, original

        d_expr = m.group("date_expr").strip()
        d_val = self._resolve_day_or_relative_name(d_expr)
        if not d_val:
            return None, original

        t1_str = m.group("t1") or m.group("t3")
        t2_str = m.group("t2") or m.group("t4")
        p1 = m.group("p1") or m.group("p3")
        p2 = m.group("p2") or m.group("p4") or p1 or "pm"
        p1 = p1 or p2

        t1 = self._parse_time_str(t1_str, p1)
        t2 = self._parse_time_str(t2_str, p2)
        if not t1 or not t2:
            return None, original

        tz = self._ref.tzinfo
        start_dt = datetime.combine(d_val, t1, tzinfo=tz)
        end_dt = datetime.combine(d_val, t2, tzinfo=tz)
        res = DateTimeRange(
            start_dt=start_dt,
            end_dt=end_dt,
            label=f"{d_expr.title()} {t1.strftime('%I:%M %p')} - {t2.strftime('%I:%M %p')}",
        )
        remaining = self._clean_span(original, m.start(), m.end())
        return res, remaining

    def _match_time_range(self, lowered: str, original: str) -> Tuple[Optional[TemporalConstraint], str]:
        # "until 10:30 tonight" / "until 10:30 pm" / "till 11 tonight"
        m_until = re.search(r"\b(?:until|till|up\s+to|by)\s+(?P<time>\d{1,2}(?::\d{2})?)\s*(?P<period>am|pm|tonight|in the evening|in the morning)?\b", lowered)
        if m_until:
            t_str = m_until.group("time")
            p_str = (m_until.group("period") or "").strip()
            period = "pm" if "tonight" in p_str or "evening" in p_str or "pm" in p_str else "am" if "morning" in p_str or "am" in p_str else "pm"
            t_val = self._parse_time_str(t_str, period)
            if t_val:
                tz = self._ref.tzinfo
                end_dt = datetime.combine(self.today, t_val, tzinfo=tz)
                start_dt = self._ref
                res = DateTimeRange(
                    start_dt=start_dt,
                    end_dt=end_dt,
                    label=f"until {t_val.strftime('%I:%M %p')} today",
                )
                remaining = self._clean_span(original, m_until.start(), m_until.end())
                return res, remaining

        # "between 2 and 6 PM" / "from 10 AM to 4 PM" / "between 10:00 and 12:30" / "from 3 to 7 this evening" / "between 4 and 8 PM yesterday"
        m_range = re.search(
            r"\b(?:between\s+(?P<t1>\d{1,2}(?::\d{2})?)\s*(?P<p1>am|pm)?\s*(?:and|to|-)\s*(?P<t2>\d{1,2}(?::\d{2})?)\s*(?P<p2>am|pm)?|"
            r"from\s+(?P<t3>\d{1,2}(?::\d{2})?)\s*(?P<p3>am|pm)?\s*(?:to|-)\s*(?P<t4>\d{1,2}(?::\d{2})?)\s*(?P<p4>am|pm)?)"
            r"(?:\s+(?P<qual>this\s+evening|tonight|this\s+afternoon|this\s+morning|yesterday|today))?\b",
            lowered,
        )
        if m_range:
            t1_str = m_range.group("t1") or m_range.group("t3")
            t2_str = m_range.group("t2") or m_range.group("t4")
            p1 = m_range.group("p1") or m_range.group("p3")
            p2 = m_range.group("p2") or m_range.group("p4")
            qual = (m_range.group("qual") or "").strip()

            if "evening" in qual or "tonight" in qual or "evening" in lowered or "tonight" in lowered:
                p2 = p2 or "pm"
                p1 = p1 or "pm"
            elif "morning" in qual or "morning" in lowered:
                p2 = p2 or "am"
                p1 = p1 or "am"
            elif "afternoon" in qual or "afternoon" in lowered:
                p2 = p2 or "pm"
                p1 = p1 or "pm"
            else:
                p1 = p1 or p2 or ""
                p2 = p2 or p1 or ""

            t1 = self._parse_time_str(t1_str, p1)
            t2 = self._parse_time_str(t2_str, p2)
            if t1 and t2:
                if qual == "yesterday":
                    y_date = self.today - timedelta(days=1)
                    res = DateTimeRange(
                        start_dt=datetime.combine(y_date, t1, tzinfo=self._ref.tzinfo),
                        end_dt=datetime.combine(y_date, t2, tzinfo=self._ref.tzinfo),
                        label=f"yesterday {t1.strftime('%I:%M %p')} - {t2.strftime('%I:%M %p')}",
                    )
                else:
                    res = TimeRange(
                        start_time=t1,
                        end_time=t2,
                        label=f"{t1.strftime('%I:%M %p')} - {t2.strftime('%I:%M %p')}",
                    )
                remaining = self._clean_span(original, m_range.start(), m_range.end())
                return res, remaining

        return None, original

    def _match_week_of_month(self, lowered: str, original: str) -> Tuple[Optional[TemporalConstraint], str]:
        # "second week of September" / "the 2nd week of september" / "first week of august 2026"
        m = re.search(
            r"\b(?:the\s+|in\s+the\s+|during\s+the\s+)?(?P<week>first|1st|second|2nd|third|3rd|fourth|4th|last|final)\s+week\s+of\s+(?P<month>[a-zA-Z]+)(?:\s+(?P<year>\d{4}))?\b",
            lowered,
        )
        if not m:
            return None, original

        w_str = m.group("week")
        m_str = m.group("month")
        y_str = m.group("year")

        week_num = ORDINAL_WEEKS.get(w_str)
        month_num = MONTHS.get(m_str)
        if not week_num or not month_num:
            return None, original

        year = int(y_str) if y_str else self.today.year
        start_day = (week_num - 1) * 7 + 1
        if week_num < 4:
            end_day = week_num * 7
        else:
            import calendar
            _, end_day = calendar.monthrange(year, month_num)
            if week_num == 4:
                end_day = min(end_day, 28)

        start_date = date(year, month_num, start_day)
        end_date = date(year, month_num, end_day)
        res = DateRange(
            start_date=start_date,
            end_date=end_date,
            label=f"{w_str.title()} week of {m_str.title()} {year}",
        )
        remaining = self._clean_span(original, m.start(), m.end())
        return res, remaining

    def _match_bounded_date_range(self, lowered: str, original: str) -> Tuple[Optional[TemporalConstraint], str]:
        # 0. "from <day1> [tod] to <day2> [tod]"
        m_from_to_dt = re.search(
            r"\bfrom\s+(?P<d1>(?:last\s+|this\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|yesterday|today))"
            r"(?:\s+(?P<tod1>morning|afternoon|evening|night))?\s+to\s+"
            r"(?P<d2>(?:last\s+|this\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|yesterday|today))"
            r"(?:\s+(?P<tod2>morning|afternoon|evening|night))?\b",
            lowered,
        )
        if m_from_to_dt:
            d1_val = self._resolve_day_or_relative_name(m_from_to_dt.group("d1"))
            d2_val = self._resolve_day_or_relative_name(m_from_to_dt.group("d2"))
            tod1 = m_from_to_dt.group("tod1")
            tod2 = m_from_to_dt.group("tod2")
            if d1_val and d2_val:
                tod_hours = {"morning": (8, 0), "afternoon": (12, 0), "evening": (20, 0), "night": (22, 0)}
                if tod1 or tod2:
                    h1, m1 = tod_hours.get(tod1 or "morning", (0, 0))
                    h2, m2 = tod_hours.get(tod2 or "evening", (23, 59))
                    res = DateTimeRange(
                        start_dt=datetime.combine(d1_val, time(h1, m1), tzinfo=self._ref.tzinfo),
                        end_dt=datetime.combine(d2_val, time(h2, m2), tzinfo=self._ref.tzinfo),
                        label=f"{m_from_to_dt.group('d1').title()} to {m_from_to_dt.group('d2').title()}",
                    )
                else:
                    res = DateRange(start_date=min(d1_val, d2_val), end_date=max(d1_val, d2_val), label=f"{d1_val} to {d2_val}")
                remaining = self._clean_span(original, m_from_to_dt.start(), m_from_to_dt.end())
                return res, remaining

        # 1. "after <date1> but before <date2>" / "since <date1> and before <date2>"
        m_after_before = re.search(
            r"\b(?:after|since)\s+(?P<d1>[a-zA-Z]+|\d{1,2}(?:st|nd|rd|th)?)\s+(?:but\s+|and\s+)?(?:before|until)\s+(?P<d2>[a-zA-Z]+|\d{1,2}(?:st|nd|rd|th)?)\b",
            lowered,
        )
        if m_after_before:
            d1_name = m_after_before.group("d1").strip()
            d2_name = m_after_before.group("d2").strip()
            d1_val = self._resolve_day_or_relative_name(d1_name)
            d2_val = self._resolve_day_or_relative_name(d2_name)
            if d1_val and d2_val:
                start_date = d1_val + timedelta(days=1) if d1_val < d2_val else d1_val
                end_date = max(start_date, d2_val)
                res = DateRange(
                    start_date=start_date,
                    end_date=end_date,
                    label=f"After {d1_name.title()} but before {d2_name.title()}",
                )
                remaining = self._clean_span(original, m_after_before.start(), m_after_before.end())
                return res, remaining

        # 2. "between <day1> and <day2>"
        m_between_days = re.search(
            r"\bbetween\s+(?P<d1>(?:last\s+|this\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\s+and\s+(?P<d2>(?:last\s+|this\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
            lowered,
        )
        if m_between_days:
            d1_name = m_between_days.group("d1")
            d2_name = m_between_days.group("d2")
            d1_val = self._resolve_day_or_relative_name(d1_name)
            d2_val = self._resolve_day_or_relative_name(d2_name)
            if d1_val and d2_val:
                if d1_val > d2_val:
                    d1_val = d1_val - timedelta(days=7)
                s_date = min(d1_val, d2_val)
                e_date = max(d1_val, d2_val)
                res = DateRange(start_date=s_date, end_date=e_date, label=f"{d1_name.title()} to {d2_name.title()}")
                remaining = self._clean_span(original, m_between_days.start(), m_between_days.end())
                return res, remaining

        # 3. "since <day/date> [tod]" / "after <day/date>"
        m_since = re.search(
            r"\b(?:since|after)\s+(?P<d>(?:last\s+|this\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|yesterday))"
            r"(?:\s+(?P<tod>morning|afternoon|evening|night))?\b",
            lowered,
        )
        if m_since:
            d_name = m_since.group("d").strip()
            tod = m_since.group("tod")
            d_val = self._resolve_day_or_relative_name(d_name)
            if d_val:
                if d_val == self.today and re.match(r"^after\b", m_since.group(0)):
                    # "after Wednesday" when today is Wednesday -> next week or future
                    s_date = self.today + timedelta(days=1)
                    e_date = s_date + timedelta(days=6)
                    res = DateRange(start_date=s_date, end_date=e_date, label=f"After {d_name.title()}")
                elif re.match(r"^after\b", m_since.group(0)):
                    start_val = d_val + timedelta(days=1)
                    res = DateRange(start_date=start_val, end_date=self.today, label=f"After {d_name.title()}")
                elif tod:
                    tod_h = {"morning": 8, "afternoon": 12, "evening": 18, "night": 20}.get(tod, 0)
                    res = DateTimeRange(
                        start_dt=datetime.combine(d_val, time(tod_h, 0), tzinfo=self._ref.tzinfo),
                        end_dt=self._ref,
                        label=f"Since {d_name.title()} {tod}",
                    )
                else:
                    res = DateRange(start_date=d_val, end_date=self.today, label=f"Since {d_name.title()}")
                remaining = self._clean_span(original, m_since.start(), m_since.end())
                return res, remaining

        # 4. "prior to <day/date> [tod]" / "before <day/date>"
        m_before = re.search(
            r"\b(?:before|prior\s+to)\s+(?P<next>next\s+)?(?P<d>(?:last\s+|this\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|yesterday|today|last\s+week))"
            r"(?:\s+(?P<tod>morning|afternoon|evening|night))?\b",
            lowered,
        )
        if m_before:
            d_name = m_before.group("d").strip()
            is_next = bool(m_before.group("next"))
            tod = m_before.group("tod")
            if d_name == "last week":
                end_val = self.today - timedelta(days=self.today.weekday() + 8)
                start_val = date(self.today.year, 8, 1) if self.today.month >= 9 else end_val - timedelta(days=30)
                res = DateRange(start_date=start_val, end_date=end_val, label="Prior to last week")
                remaining = self._clean_span(original, m_before.start(), m_before.end())
                return res, remaining

            d_val = self._resolve_day_or_relative_name(d_name)
            if d_val:
                if is_next:
                    # e.g. "before next Monday"
                    target_w = DAYS_OF_WEEK.get(d_name, 0)
                    days_ahead = (target_w - self.today.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    target_d = self.today + timedelta(days=days_ahead)
                    res = DateRange(start_date=self.today, end_date=target_d - timedelta(days=1), label=f"Before next {d_name.title()}")
                elif tod:
                    tod_h = {"morning": 8, "afternoon": 12, "evening": 18, "night": 20}.get(tod, 0)
                    res = DateTimeRange(
                        start_dt=datetime.combine(date(self.today.year, self.today.month, 1), time.min, tzinfo=self._ref.tzinfo),
                        end_dt=datetime.combine(d_val, time(tod_h, 0), tzinfo=self._ref.tzinfo),
                        label=f"Prior to {d_name.title()} {tod}",
                    )
                else:
                    end_val = d_val - timedelta(days=1)
                    start_val = date(self.today.year, self.today.month, 1)
                    res = DateRange(start_date=start_val, end_date=end_val, label=f"Before {d_name.title()}")
                remaining = self._clean_span(original, m_before.start(), m_before.end())
                return res, remaining

        return None, original

    def _match_relative_interval(self, lowered: str, original: str) -> Tuple[Optional[TemporalConstraint], str]:
        # "since N days ago"
        m_since_ago = re.search(r"\bsince\s+(?P<n>\d+|two|three|four|five)\s+days?\s+ago\b", lowered)
        if m_since_ago:
            n_raw = m_since_ago.group("n")
            w_map = {"two": 2, "three": 3, "four": 4, "five": 5}
            n = w_map.get(n_raw, int(n_raw) if n_raw.isdigit() else 2)
            start_date = self.today - timedelta(days=n)
            res = DateRange(start_date=start_date, end_date=self.today, label=f"Since {n} days ago")
            remaining = self._clean_span(original, m_since_ago.start(), m_since_ago.end())
            return res, remaining

        # "N days ago"
        m_ago = re.search(r"\b(?P<n>\d+|two|three|four|five)\s+days?\s+ago\b", lowered)
        if m_ago:
            n_raw = m_ago.group("n")
            w_map = {"two": 2, "three": 3, "four": 4, "five": 5}
            n = w_map.get(n_raw, int(n_raw) if n_raw.isdigit() else 2)
            resolved = self.today - timedelta(days=n)
            res = DatePoint(resolved_date=resolved, label=f"{n} days ago")
            remaining = self._clean_span(original, m_ago.start(), m_ago.end())
            return res, remaining

        # "during mid <month>" / "mid September"
        m_mid = re.search(r"\b(?:during\s+|in\s+)?mid\s+(?P<m>[a-zA-Z]+)\b", lowered)
        if m_mid:
            m_str = m_mid.group("m")
            m_num = MONTHS.get(m_str)
            if m_num:
                res = DateRange(start_date=date(self.today.year, m_num, 11), end_date=date(self.today.year, m_num, 20), label=f"Mid {m_str.title()}")
                remaining = self._clean_span(original, m_mid.start(), m_mid.end())
                return res, remaining

        # "last night [around N]"
        m_last_night = re.search(r"\blast\s+night(?:\s+around\s+(?P<hr>\d{1,2}))?\b", lowered)
        if m_last_night:
            hr_str = m_last_night.group("hr")
            hr = int(hr_str) if hr_str else 20
            if hr < 12:
                hr += 12
            y_date = self.today - timedelta(days=1)
            res = DateTimePoint(resolved_dt=datetime.combine(y_date, time(hr, 0), tzinfo=self._ref.tzinfo), label="last night")
            remaining = self._clean_span(original, m_last_night.start(), m_last_night.end())
            return res, remaining

        # "saved last Saturday afternoon"
        m_last_day_tod = re.search(r"\b(?:last|past)\s+(?P<day>monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?P<tod>morning|afternoon|evening|night)\b", lowered)
        if m_last_day_tod:
            d_name = m_last_day_tod.group("day")
            tod = m_last_day_tod.group("tod")
            d_val = self._resolve_day_or_relative_name(f"last {d_name}")
            if d_val:
                tod_spans = {"morning": (8, 12), "afternoon": (12, 18), "evening": (18, 22), "night": (20, 23)}
                sh, eh = tod_spans.get(tod, (12, 18))
                res = DateTimeRange(
                    start_dt=datetime.combine(d_val, time(sh, 0), tzinfo=self._ref.tzinfo),
                    end_dt=datetime.combine(d_val, time(eh, 0), tzinfo=self._ref.tzinfo),
                    label=f"last {d_name.title()} {tod}",
                )
                remaining = self._clean_span(original, m_last_day_tod.start(), m_last_day_tod.end())
                return res, remaining

        # "past N days" / "last N days" / "last N hours" / "last 24 hours" / "within the last 48 hours"
        m_past = re.search(
            r"\b(?:within\s+the\s+|in\s+the\s+|over\s+the\s+)?(?:past|last)\s+(?P<n>\d+|two|three|four|five|six|seven|ten|fourteen|twenty-four|forty-eight)\s+(?P<u>days?|weeks?|months?|hours?)\b",
            lowered,
        )
        if m_past:
            n_raw = m_past.group("n")
            u_raw = m_past.group("u")
            word_to_num = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10, "fourteen": 14, "twenty-four": 24, "forty-eight": 48}
            n = word_to_num.get(n_raw, int(n_raw) if n_raw.isdigit() else 1)
            if "hour" in u_raw:
                days = max(1, n // 24)
            elif "week" in u_raw:
                days = n * 7
            elif "month" in u_raw:
                days = n * 30
            else:
                days = n
            start_date = self.today - timedelta(days=days)
            res = DateRange(start_date=start_date, end_date=self.today, label=f"Past {n} {u_raw}")
            remaining = self._clean_span(original, m_past.start(), m_past.end())
            return res, remaining

        # "last weekend"
        if re.search(r"\blast\s+weekend\b", lowered):
            m = re.search(r"\blast\s+weekend\b", lowered)
            cur_weekday = self.today.weekday()
            days_since_sunday = (cur_weekday - 6) % 7
            if days_since_sunday == 0:
                days_since_sunday = 7
            last_sunday = self.today - timedelta(days=days_since_sunday)
            last_saturday = last_sunday - timedelta(days=1)
            res = DateRange(start_date=last_saturday, end_date=last_sunday, label="Last weekend")
            remaining = self._clean_span(original, m.start(), m.end())
            return res, remaining

        # "earlier this month"
        if re.search(r"\bearlier\s+this\s+month\b", lowered):
            m = re.search(r"\bearlier\s+this\s+month\b", lowered)
            start_date = date(self.today.year, self.today.month, 1)
            res = DateRange(start_date=start_date, end_date=self.today - timedelta(days=1), label="Earlier this month")
            remaining = self._clean_span(original, m.start(), m.end())
            return res, remaining

        # "earlier today"
        if re.search(r"\bearlier\s+today\b", lowered):
            m = re.search(r"\bearlier\s+today\b", lowered)
            res = DatePoint(resolved_date=self.today, label="earlier today")
            remaining = self._clean_span(original, m.start(), m.end())
            return res, remaining

        return None, original

    def _match_single_relative_date(self, lowered: str, original: str) -> Tuple[Optional[TemporalConstraint], str]:
        m_tomorrow = re.search(r"\b(?:on\s+)?tomorrow\b", lowered)
        if m_tomorrow:
            return DatePoint(self.today + timedelta(days=1), "tomorrow"), self._clean_span(original, m_tomorrow.start(), m_tomorrow.end())
        # "yesterday"
        m_yest = re.search(r"\b(?:from\s+|on\s+)?yesterday\b", lowered)
        if m_yest:
            y_date = self.today - timedelta(days=1)
            res = DatePoint(resolved_date=y_date, label="yesterday")
            remaining = self._clean_span(original, m_yest.start(), m_yest.end())
            return res, remaining

        # "today"
        m_today = re.search(r"\b(?:from\s+|on\s+)?today\b", lowered)
        if m_today and not re.search(r"\b(?:days\s+from\s+today|weeks\s+from\s+today)\b", lowered):
            res = DatePoint(resolved_date=self.today, label="today")
            remaining = self._clean_span(original, m_today.start(), m_today.end())
            return res, remaining

        # "last Tuesday" / "last Friday" / "past Monday"
        m_last_day = re.search(r"\b(?:from\s+|on\s+)?(?:last|past)\s+(?P<day>monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered)
        if m_last_day:
            day_name = m_last_day.group("day")
            target_weekday = DAYS_OF_WEEK[day_name]
            cur_weekday = self.today.weekday()
            days_ago = (cur_weekday - target_weekday) % 7
            if target_weekday <= cur_weekday:
                days_ago += 7
            resolved = self.today - timedelta(days=days_ago)
            res = DatePoint(resolved_date=resolved, label=f"last {day_name.title()}")
            remaining = self._clean_span(original, m_last_day.start(), m_last_day.end())
            return res, remaining

        # Bare day of the week: "Monday", "on Tuesday", "this Friday"
        m_bare_day = re.search(r"\b(?:from\s+|on\s+|this\s+)?(?P<day>monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered)
        if m_bare_day:
            day_name = m_bare_day.group("day")
            target_weekday = DAYS_OF_WEEK[day_name]
            cur_weekday = self.today.weekday()
            # Most recent past occurrence (or today if same day)
            days_ago = (cur_weekday - target_weekday) % 7
            if days_ago == 0 and "this" not in m_bare_day.group(0):
                # If said on Wednesday, "Wednesday" is today
                days_ago = 0
            resolved = self.today - timedelta(days=days_ago)
            res = DatePoint(resolved_date=resolved, label=day_name.title())
            remaining = self._clean_span(original, m_bare_day.start(), m_bare_day.end())
            return res, remaining

        return None, original

    def _resolve_day_or_relative_name(self, name: str) -> Optional[date]:
        """Resolves a named day or relative token into a concrete calendar date."""
        n = name.strip().lower()
        if n == "yesterday":
            return self.today - timedelta(days=1)
        if n in ("today", "now"):
            return self.today
        if n == "tomorrow":
            return self.today + timedelta(days=1)

        m_last = re.match(r"^(?:last|past)\s+([a-zA-Z]+)$", n)
        if m_last:
            day_token = m_last.group(1)
            if day_token in DAYS_OF_WEEK:
                target_weekday = DAYS_OF_WEEK[day_token]
                cur_weekday = self.today.weekday()
                days_ago = (cur_weekday - target_weekday) % 7
                if target_weekday <= cur_weekday:
                    days_ago += 7
                return self.today - timedelta(days=days_ago)

        m_this = re.match(r"^(?:this\s+)?([a-zA-Z]+)$", n)
        if m_this:
            day_token = m_this.group(1)
            if day_token in DAYS_OF_WEEK:
                target_weekday = DAYS_OF_WEEK[day_token]
                cur_weekday = self.today.weekday()
                days_ago = (cur_weekday - target_weekday) % 7
                return self.today - timedelta(days=days_ago)

        return None

    def _parse_time_str(self, time_str: str, period: str) -> Optional[time]:
        """Parses a time string like '2', '2:30', '14:00' with am/pm period."""
        if not time_str:
            return None
        t_clean = time_str.strip()
        parts = t_clean.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            return None

        p = period.lower().strip()
        if p == "pm" and hour < 12:
            hour += 12
        elif p == "am" and hour == 12:
            hour = 0

        try:
            return time(hour, minute)
        except ValueError:
            return None
