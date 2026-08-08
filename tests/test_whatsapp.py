# -*- coding: utf-8 -*-
import datetime as dt
from types import SimpleNamespace
from urllib.parse import unquote

from whatsapp import build_task_message, build_weekly_message, build_wa_link

TODAY = dt.date(2026, 7, 25)


def make_task(title="", original_text="", assignee=None, deadline=None, urgent=False):
    return SimpleNamespace(
        title=title, original_text=original_text, assignee=assignee,
        deadline=deadline, urgent=urgent,
    )


# ---------- build_task_message ----------

def test_task_message_includes_all_fields():
    task = make_task(title="לתאם שיחה", assignee="דנה כהן - י'4", deadline="2026-07-28", urgent=True)
    msg = build_task_message(task)
    assert "לתאם שיחה" in msg
    assert "דנה כהן - י'4" in msg
    assert "2026-07-28" in msg
    assert "דחוף" in msg


def test_task_message_omits_missing_fields():
    task = make_task(title="לתאם שיחה", assignee=None, deadline=None, urgent=False)
    msg = build_task_message(task)
    assert "עבור" not in msg
    assert "תאריך יעד" not in msg
    assert "דחוף" not in msg


def test_task_message_falls_back_to_original_text_when_no_title():
    task = make_task(title="", original_text="הטקסט המקורי", assignee=None, deadline=None)
    msg = build_task_message(task)
    assert "הטקסט המקורי" in msg


# ---------- build_weekly_message ----------

def test_weekly_message_includes_tasks_within_seven_days():
    tasks = [
        make_task(title="משימה קרובה", deadline="2026-07-30"),
        make_task(title="משימה רחוקה", deadline="2026-09-01"),
    ]
    msg = build_weekly_message(tasks, today=TODAY)
    assert "משימה קרובה" in msg
    assert "משימה רחוקה" not in msg


def test_weekly_message_excludes_tasks_without_deadline():
    tasks = [make_task(title="בלי דדליין", deadline=None)]
    msg = build_weekly_message(tasks, today=TODAY)
    assert "בלי דדליין" not in msg


def test_weekly_message_sorted_by_deadline():
    tasks = [
        make_task(title="שנייה", deadline="2026-07-29"),
        make_task(title="ראשונה", deadline="2026-07-26"),
    ]
    msg = build_weekly_message(tasks, today=TODAY)
    assert msg.index("ראשונה") < msg.index("שנייה")


def test_weekly_message_empty_when_no_relevant_tasks():
    msg = build_weekly_message([], today=TODAY)
    assert "אין משימות" in msg


def test_weekly_message_marks_urgent_tasks():
    tasks = [make_task(title="דחופה", deadline="2026-07-26", urgent=True)]
    msg = build_weekly_message(tasks, today=TODAY)
    assert "🔴" in msg


# ---------- build_wa_link ----------

def test_wa_link_url_encodes_message():
    link = build_wa_link("שלום עולם")
    assert link.startswith("https://wa.me/?text=")
    assert unquote(link.split("text=")[1]) == "שלום עולם"
