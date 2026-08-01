# -*- coding: utf-8 -*-
"""
מנוע פענוח מבוסס-חוקים (בלי AI, בלי תלות חיצונית).
כל פונקציית extract_* מחזירה (value, matched_span) כדי שנוכל להסיר את הקטע
שזוהה מתוך הטקסט לצורך בניית "כותרת" נקייה יותר.
"""
import re
import datetime as dt
from typing import Optional, Tuple, List

URGENT_PATTERN = re.compile(r"\bדחוף\b|\bדחופ(ה|ות)\b|\bבדחיפות\b|\bבהול(ה|ים|ות)?\b")

WEEKDAY_MAP = {
    "ראשון": 6, "שני": 0, "שלישי": 1, "רביעי": 2,
    "חמישי": 3, "שישי": 4, "שבת": 5,
}
WEEKDAY_PATTERN = re.compile(r"יום\s+(" + "|".join(WEEKDAY_MAP.keys()) + r")")

RELATIVE_PATTERNS = [
    (re.compile(r"היום"), 0),
    (re.compile(r"מחרתיים"), 2),
    (re.compile(r"מחר"), 1),
    (re.compile(r"בעוד\s+יומיים"), 2),
    (re.compile(r"בעוד\s+שבועיים"), 14),
    (re.compile(r"בעוד\s+שבוע"), 7),
    (re.compile(r"בעוד\s+(\d+)\s+ימים"), None),   # מספר דינמי - מטופל בנפרד
    (re.compile(r"עד\s+סוף\s+השבוע"), "end_of_week"),
]

EXPLICIT_DATE_PATTERN = re.compile(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b")

CLASS_PATTERN = re.compile(r"י[\'\u05f3\u05f4\-]?\s?[1-7]\b")


def _next_weekday(target_py_weekday: int, today: dt.date) -> dt.date:
    days_ahead = (target_py_weekday - today.weekday()) % 7
    return today + dt.timedelta(days=days_ahead)


def extract_urgent(text: str) -> Tuple[bool, Optional[Tuple[int, int]]]:
    m = URGENT_PATTERN.search(text)
    if m:
        return True, m.span()
    return False, None


def extract_deadline(text: str, today: Optional[dt.date] = None) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    today = today or dt.date.today()

    # תאריך מפורש (DD/MM/YYYY או DD.MM) - קודם, כי הוא הכי חד-משמעי
    m = EXPLICIT_DATE_PATTERN.search(text)
    if m:
        day, month, year = m.groups()
        day, month = int(day), int(month)
        year = int(year) if year else today.year
        if year < 100:
            year += 2000
        try:
            candidate = dt.date(year, month, day)
            if not m.group(3) and candidate < today - dt.timedelta(days=30):
                candidate = dt.date(year + 1, month, day)
            return candidate.isoformat(), m.span()
        except ValueError:
            pass  # תאריך לא תקין (למשל 31/02) - מתעלמים וממשיכים לחוקים הבאים

    # יום בשבוע ("עד יום רביעי")
    m = WEEKDAY_PATTERN.search(text)
    if m:
        day_name = m.group(1)
        candidate = _next_weekday(WEEKDAY_MAP[day_name], today)
        return candidate.isoformat(), m.span()

    # "בעוד N ימים"
    m = re.search(r"בעוד\s+(\d+)\s+ימים", text)
    if m:
        n = int(m.group(1))
        return (today + dt.timedelta(days=n)).isoformat(), m.span()

    # שאר הביטויים היחסיים
    for pattern, offset in RELATIVE_PATTERNS:
        if offset is None:
            continue
        m = pattern.search(text)
        if m:
            if offset == "end_of_week":
                candidate = _next_weekday(WEEKDAY_MAP["שישי"], today)
            else:
                candidate = today + dt.timedelta(days=offset)
            return candidate.isoformat(), m.span()

    return None, None


def extract_assignee(text: str, alias_rules: List[Tuple[str, str]]) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """
    alias_rules: רשימת (pattern, value) שהרכז הגדיר במסך התבניות.
    נבדקים קודם - כי הם ספציפיים ונוצרו במכוון על ידי המשתמש.
    """
    for pattern, value in alias_rules:
        idx = text.find(pattern)
        if idx != -1:
            return value, (idx, idx + len(pattern))

    m = CLASS_PATTERN.search(text)
    if m:
        normalized = "י'" + re.search(r"[1-7]", m.group()).group()
        return normalized, m.span()

    return None, None


def _strip_span(text: str, span: Optional[Tuple[int, int]]) -> str:
    if not span:
        return text
    return (text[:span[0]] + " " + text[span[1]:]).strip()


def build_title(text: str, spans_to_remove: List[Optional[Tuple[int, int]]]) -> str:
    cleaned = text
    # מסירים מהסוף להתחלה כדי לא לקלקל אינדקסים
    for span in sorted([s for s in spans_to_remove if s], key=lambda s: -s[0]):
        cleaned = cleaned[:span[0]] + " " + cleaned[span[1]:]
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned if cleaned else text.strip()


def parse_task(text: str, alias_rules: Optional[List[Tuple[str, str]]] = None) -> dict:
    alias_rules = alias_rules or []
    urgent, urgent_span = extract_urgent(text)
    deadline, deadline_span = extract_deadline(text)
    assignee, assignee_span = extract_assignee(text, alias_rules)
    title = build_title(text, [urgent_span, deadline_span, assignee_span])

    return {
        "title": title,
        "original_text": text,
        "assignee": assignee,
        "deadline": deadline,
        "urgent": urgent,
    }
