# -*- coding: utf-8 -*-
"""
בניית הודעות ייצוא לווטסאפ.
לא שולח כלום בעצמו - רק בונה טקסט וקישור wa.me; המשתמש בוחר למי לשלוח
בתוך ווטסאפ עצמו וללוחץ שלח.
"""
import datetime as dt
from urllib.parse import quote


def build_task_message(task) -> str:
    lines = [f"📋 *{task.title or task.original_text}*"]
    if task.assignee:
        lines.append(f"👤 עבור: {task.assignee}")
    if task.deadline:
        lines.append(f"📅 תאריך יעד: {task.deadline}")
    if task.urgent:
        lines.append("🔴 דחוף")
    return "\n".join(lines)


def build_weekly_message(tasks, today=None) -> str:
    today = today or dt.date.today()
    end = today + dt.timedelta(days=7)
    relevant = [
        t for t in tasks
        if t.deadline and today.isoformat() <= t.deadline <= end.isoformat()
    ]
    relevant.sort(key=lambda t: t.deadline)

    lines = [f"📋 סיכום משימות לשבוע הקרוב ({today.isoformat()} - {end.isoformat()}):", ""]
    if not relevant:
        lines.append("אין משימות עם תאריך יעד השבוע.")
    else:
        for i, t in enumerate(relevant, start=1):
            urgent_tag = " 🔴" if t.urgent else ""
            lines.append(f"{i}. *{t.title or t.original_text}* - 📅 {t.deadline}{urgent_tag}")
    return "\n".join(lines)


def build_wa_link(message: str) -> str:
    return "https://wa.me/?text=" + quote(message)
