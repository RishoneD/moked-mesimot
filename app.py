# -*- coding: utf-8 -*-
import datetime as dt
import streamlit as st
from sqlalchemy import select

from db import init_db, get_session, Task, Rule, ALL_STATUSES, STATUS_PENDING, STATUS_CLOSED
from parser import parse_task

st.set_page_config(page_title="ניהול משימות - רכז שכבה", layout="wide")

# ---------- עיצוב RTL ----------
st.markdown(
    """
    <style>
    [data-testid="stMain"] { direction: rtl; }
    .stTextArea textarea, .stTextInput input, .stDateInput input { direction: rtl; text-align: right; }
    .urgent-badge { background:#e74c3c; color:white; padding:2px 8px; border-radius:8px; font-size:0.8em; }
    </style>
    """,
    unsafe_allow_html=True,
)

init_db()


def get_alias_rules(session):
    rules = session.execute(select(Rule).where(Rule.rule_type == "assignee_alias")).scalars().all()
    return [(r.pattern, r.value) for r in rules]


# ---------- ניווט ----------
st.sidebar.title("📋 ניהול משימות שכבה")
page = st.sidebar.radio(
    "בחר מסך",
    ["➕ הוספת משימה", "✅ תור בדיקה", "📑 כל המשימות", "⚙️ תבניות וחוקים"],
)

session = get_session()

# ============================================================
# מסך 1: הוספת משימה
# ============================================================
if page == "➕ הוספת משימה":
    st.header("הוספת משימה חדשה")
    st.caption("כתוב את המשימה במשפט חופשי - המערכת תנסה לזהות למי מיועד, דדליין ודחיפות. "
               "כל משימה חדשה תמתין לאישורך בתור הבדיקה.")

    if "new_task_input_version" not in st.session_state:
        st.session_state["new_task_input_version"] = 0
    input_key = f"new_task_text_{st.session_state['new_task_input_version']}"

    text = st.text_area(
        "משימה חדשה", height=100,
        placeholder="לדוגמה: לתאם עם המחנכת של י'2 שיחה עם הורה עד יום רביעי - דחוף",
        key=input_key,
    )

    col1, col2 = st.columns([2, 1])
    add_clicked = col1.button("הוסף לתור הבדיקה", type="primary", disabled=not text.strip())
    reset_clicked = col2.button("איפוס")

    if add_clicked:
        alias_rules = get_alias_rules(session)
        parsed = parse_task(text.strip(), alias_rules)
        task = Task(
            title=parsed["title"],
            original_text=parsed["original_text"],
            assignee=parsed["assignee"],
            deadline=parsed["deadline"],
            urgent=parsed["urgent"],
            status=STATUS_PENDING,
        )
        session.add(task)
        session.commit()
        st.session_state["new_task_input_version"] += 1
        st.success("המשימה נוספה לתור הבדיקה ✅")
        st.rerun()

    if reset_clicked:
        st.session_state["new_task_input_version"] += 1
        st.rerun()

# ============================================================
# מסך 2: תור בדיקה (הכל ממתין לאישור עד שהרכז יעבור עליו)
# ============================================================
elif page == "✅ תור בדיקה":
    st.header("תור בדיקה - משימות הממתינות לאישור")
    pending = session.execute(
        select(Task).where(Task.status == STATUS_PENDING).order_by(Task.created_at)
    ).scalars().all()

    if not pending:
        st.info("אין משימות ממתינות כרגע 🎉")

    for task in pending:
        with st.container(border=True):
            urgent_tag = " 🔴 דחוף" if task.urgent else ""
            st.markdown(f"**טקסט מקורי:** {task.original_text}{urgent_tag}")
            col1, col2, col3, col4 = st.columns(4)
            new_title = col1.text_input("כותרת", value=task.title or "", key=f"title_{task.id}")
            new_assignee = col2.text_input("למי מיועד", value=task.assignee or "", key=f"assignee_{task.id}")
            try:
                default_deadline = dt.date.fromisoformat(task.deadline) if task.deadline else None
            except ValueError:
                default_deadline = None
            new_deadline = col3.date_input("דדליין", value=default_deadline, key=f"deadline_{task.id}")
            new_urgent = col4.checkbox("דחוף", value=task.urgent, key=f"urgent_{task.id}")

            new_status = st.selectbox(
                "העבר לסטטוס",
                [s for s in ALL_STATUSES if s != STATUS_PENDING],
                key=f"status_{task.id}",
            )
            notes = st.text_input("הערות (פרטי, לא מיוצא)", value=task.coordinator_notes or "", key=f"notes_{task.id}")

            b1, b2 = st.columns(2)
            if b1.button("אשר ✅", key=f"approve_{task.id}"):
                task.title = new_title
                task.assignee = new_assignee or None
                task.deadline = new_deadline.isoformat() if new_deadline else None
                task.urgent = new_urgent
                task.status = new_status
                task.coordinator_notes = notes
                session.commit()
                st.rerun()
            if b2.button("מחק 🗑️", key=f"delete_{task.id}"):
                session.delete(task)
                session.commit()
                st.rerun()

# ============================================================
# מסך 3: כל המשימות (בשלב זה - גם תצוגת המחנכים, פתוח לכולם)
# ============================================================
elif page == "📑 כל המשימות":
    st.header("כל המשימות")
    status_filter = st.multiselect("סינון לפי סטטוס", ALL_STATUSES, default=ALL_STATUSES)
    query = select(Task).order_by(Task.urgent.desc(), Task.deadline.is_(None), Task.deadline)
    tasks = session.execute(query).scalars().all()
    tasks = [t for t in tasks if t.status in status_filter]

    if not tasks:
        st.info("אין משימות להצגה.")

    for task in tasks:
        with st.container(border=True):
            c_badge, c_title, c_assignee, c_deadline, c_status, c_update, c_return = st.columns(
                [0.6, 3, 1.6, 1.3, 1.6, 0.6, 0.6]
            )
            c_badge.markdown("🔴" if task.urgent else "")
            c_title.markdown(f"**{task.title or task.original_text}**")
            c_assignee.caption(f"👤 {task.assignee}" if task.assignee else "")
            c_deadline.caption(f"📅 {task.deadline}" if task.deadline else "")

            status_key = f"all_status_{task.id}"
            new_status = c_status.selectbox(
                "סטטוס", ALL_STATUSES,
                index=ALL_STATUSES.index(task.status),
                key=status_key,
                label_visibility="collapsed",
            )
            if c_update.button("✓", key=f"all_update_{task.id}", help="עדכן סטטוס"):
                task.status = new_status
                session.commit()
                st.rerun()
            if task.status != STATUS_PENDING:
                if c_return.button("↩️", key=f"all_return_{task.id}", help="החזר לתור בדיקה"):
                    task.status = STATUS_PENDING
                    session.commit()
                    st.rerun()

# ============================================================
# מסך 4: תבניות וחוקים - כאן נצבר "הידע" שהרכז מוסיף ידנית
# ============================================================
elif page == "⚙️ תבניות וחוקים":
    st.header("תבניות וחוקים")
    st.caption("כשמנוע הפענוח לא מזהה נכון את מי שהמשימה מיועדת לו, אפשר להוסיף כאן כלל קבוע: "
               "טקסט שיופיע במשימות עתידיות → הערך שאליו הוא ימופה אוטומטית.")

    with st.form("add_rule"):
        col1, col2 = st.columns(2)
        pattern = col1.text_input("מה יופיע בטקסט (למשל: 'המורה דנה')")
        value = col2.text_input("למה זה ימופה (למשל: 'דנה כהן - י\'4')")
        submitted = st.form_submit_button("הוסף כלל")
        if submitted and pattern and value:
            session.add(Rule(rule_type="assignee_alias", pattern=pattern, value=value))
            session.commit()
            st.success("הכלל נוסף")
            st.rerun()

    st.subheader("כללים קיימים")
    rules = session.execute(select(Rule)).scalars().all()
    if not rules:
        st.info("עדיין לא הוגדרו כללים.")
    for r in rules:
        c1, c2, c3 = st.columns([3, 3, 1])
        c1.write(r.pattern)
        c2.write(r.value)
        if c3.button("מחק", key=f"delrule_{r.id}"):
            session.delete(r)
            session.commit()
            st.rerun()

session.close()
