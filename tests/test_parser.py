# -*- coding: utf-8 -*-
import datetime as dt

from parser import (
    extract_urgent,
    extract_deadline,
    extract_assignee,
    build_title,
    parse_task,
)

TODAY = dt.date(2026, 7, 25)  # Saturday


# ---------- extract_urgent ----------

def test_urgent_basic():
    assert extract_urgent("לתאם פגישה - דחוף")[0] is True


def test_urgent_feminine_form():
    assert extract_urgent("משימה דחופה")[0] is True


def test_urgent_plural_form():
    assert extract_urgent("משימות דחופות")[0] is True


def test_urgent_bidchiput_form():
    assert extract_urgent("לטפל בדחיפות")[0] is True


def test_urgent_absent():
    urgent, span = extract_urgent("לתאם פגישה רגילה")
    assert urgent is False
    assert span is None


# ---------- extract_deadline: weekday ----------

def test_deadline_next_weekday():
    # today is Saturday 2026-07-25; next Tuesday is 2026-07-28
    deadline, span = extract_deadline("עד יום שלישי", today=TODAY)
    assert deadline == "2026-07-28"
    assert span is not None


def test_deadline_same_weekday_as_today_returns_today():
    deadline, _ = extract_deadline("עד יום שבת", today=TODAY)
    assert deadline == TODAY.isoformat()


# ---------- extract_deadline: relative ----------

def test_deadline_today():
    deadline, _ = extract_deadline("היום", today=TODAY)
    assert deadline == "2026-07-25"


def test_deadline_tomorrow():
    deadline, _ = extract_deadline("מחר", today=TODAY)
    assert deadline == "2026-07-26"


def test_deadline_day_after_tomorrow():
    deadline, _ = extract_deadline("מחרתיים", today=TODAY)
    assert deadline == "2026-07-27"


def test_deadline_beod_yomayim():
    deadline, _ = extract_deadline("בעוד יומיים", today=TODAY)
    assert deadline == "2026-07-27"


def test_deadline_beod_n_yamim():
    deadline, _ = extract_deadline("בעוד 5 ימים", today=TODAY)
    assert deadline == "2026-07-30"


def test_deadline_beod_shavua():
    deadline, _ = extract_deadline("בעוד שבוע", today=TODAY)
    assert deadline == "2026-08-01"


def test_deadline_beod_shvuayim():
    deadline, _ = extract_deadline("בעוד שבועיים", today=TODAY)
    assert deadline == "2026-08-08"


def test_deadline_end_of_week():
    # next Friday from Saturday 2026-07-25 is 2026-07-31
    deadline, _ = extract_deadline("עד סוף השבוע", today=TODAY)
    assert deadline == "2026-07-31"


# ---------- extract_deadline: explicit dates ----------

def test_deadline_explicit_date_with_year():
    deadline, _ = extract_deadline("עד 15/8/2027", today=TODAY)
    assert deadline == "2027-08-15"


def test_deadline_explicit_date_no_year_future_this_year():
    deadline, _ = extract_deadline("עד 5/12", today=TODAY)
    assert deadline == "2026-12-05"


def test_deadline_explicit_date_no_year_rolls_to_next_year():
    # Jan 5th is more than 30 days in the past relative to July 25 -> rolls to 2027
    deadline, _ = extract_deadline("עד 5/1", today=TODAY)
    assert deadline == "2027-01-05"


def test_deadline_explicit_date_dot_separator():
    deadline, _ = extract_deadline("עד 15.8", today=TODAY)
    assert deadline == "2026-08-15"


def test_deadline_invalid_explicit_date_falls_through():
    # 31/2 is not a valid date -> should be ignored, weekday rule should win
    deadline, _ = extract_deadline("עד 31/2 אבל בפועל עד יום שלישי", today=TODAY)
    assert deadline == "2026-07-28"


def test_deadline_none_when_no_cue():
    deadline, span = extract_deadline("לתאם פגישה עם ההורים", today=TODAY)
    assert deadline is None
    assert span is None


# ---------- extract_assignee ----------

def test_assignee_alias_rule_takes_priority():
    rules = [("המורה דנה", "דנה כהן - י'4")]
    assignee, _ = extract_assignee("לתאם עם המורה דנה שיחה", rules)
    assert assignee == "דנה כהן - י'4"


def test_assignee_class_pattern_with_geresh():
    assignee, _ = extract_assignee("שיחה עם י'2 בנושא משמעת", [])
    assert assignee == "י'2"


def test_assignee_class_pattern_no_geresh():
    assignee, _ = extract_assignee("שיחה עם י2 בנושא משמעת", [])
    assert assignee == "י'2"


def test_assignee_none_when_no_match():
    assignee, span = extract_assignee("לתאם פגישה כללית", [])
    assert assignee is None
    assert span is None


def test_assignee_alias_checked_before_class_pattern():
    # text contains both an alias match and a class-number pattern;
    # the alias rule (specific, user-defined) should win.
    rules = [("המחנכת של י”7", "רותי לוי")]
    assignee, _ = extract_assignee("לתאם עם המחנכת של י”7 שיחה", rules)
    assert assignee == "רותי לוי"


# ---------- build_title ----------

def test_build_title_strips_matched_spans():
    text = "לתאם עם המורה דנה שיחה עם הורה עד יום שלישי - דחוף"
    urgent_span = extract_urgent(text)[1]
    deadline_span = extract_deadline(text, today=TODAY)[1]
    title = build_title(text, [urgent_span, deadline_span])
    assert title == "לתאם עם המורה דנה שיחה עם הורה עד"


def test_build_title_falls_back_to_original_when_everything_removed():
    text = "דחוף"
    urgent_span = extract_urgent(text)[1]
    title = build_title(text, [urgent_span])
    assert title == "דחוף"


# ---------- parse_task (integration) ----------

def test_parse_task_full_example_no_rules():
    text = "לתאם עם המורה דנה שיחה עם הורה עד יום שלישי - דחוף"
    result = parse_task(text)
    assert result["title"] == "לתאם עם המורה דנה שיחה עם הורה עד"
    assert result["original_text"] == text
    assert result["assignee"] is None
    assert result["urgent"] is True
    # deadline depends on real today(); just check it parsed to a valid ISO date
    dt.date.fromisoformat(result["deadline"])


def test_parse_task_with_alias_rule():
    rules = [("המורה דנה", "דנה כהן - י'4")]
    result = parse_task("להזכיר להמורה דנה לשלוח דוח מחר", rules)
    assert result["assignee"] == "דנה כהן - י'4"
    assert result["title"] == "להזכיר ל לשלוח דוח"
    assert result["urgent"] is False


def test_parse_task_empty_alias_rules_defaults_to_none():
    result = parse_task("לתאם פגישה כללית")
    assert result["assignee"] is None
    assert result["urgent"] is False
    assert result["deadline"] is None
    assert result["title"] == "לתאם פגישה כללית"
