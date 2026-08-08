# -*- coding: utf-8 -*-
import os
import datetime as dt
import streamlit as st
from sqlalchemy import select

from db import init_db, get_session, Task, Rule, Teacher, ALL_STATUSES, STATUS_PENDING, STATUS_CLOSED
from parser import parse_task
from whatsapp import build_task_message, build_weekly_message, build_wa_link

APP_VERSION = "v0.4.1"

# קוד גישה לרכז/ת - בפרודקשן מוגדר כ-secret ב-Streamlit Cloud, לא בקוד.
# "changeme" הוא ברירת מחדל לפיתוח מקומי בלבד.
COORDINATOR_CODE = os.environ.get("COORDINATOR_CODE", "changeme")

st.set_page_config(page_title="ניהול משימות - רכז שכבה", layout="wide")

# ---------- עיצוב RTL ----------
st.markdown(
    """
    <style>
    [data-testid="stMain"] { direction: rtl; }
    [data-testid="stHeadingWithActionElements"] { text-align: right; }
    .stTextArea textarea, .stTextInput input, .stDateInput input { direction: rtl; text-align: right; }
    .urgent-badge { background:#e74c3c; color:white; padding:2px 8px; border-radius:8px; font-size:0.8em; }
    </style>
    """,
    unsafe_allow_html=True,
)

init_db()
session = get_session()


def get_alias_rules(session):
    rules = session.execute(select(Rule).where(Rule.rule_type == "assignee_alias")).scalars().all()
    return [(r.pattern, r.value) for r in rules]


# ============================================================
# כניסה - בחירת תפקיד וקוד גישה
# ============================================================
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    st.title("📋 ניהול משימות שכבה")

    if "login_choice" not in st.session_state:
        st.session_state.login_choice = None

    st.write("מי את/ה?")
    col1, col2 = st.columns(2)
    if col1.button("🧑‍💼\n\n**אני רכז/ת**", use_container_width=True):
        st.session_state.login_choice = "coordinator"
    if col2.button("🧑‍🏫\n\n**אני מחנכ/ת**", use_container_width=True):
        st.session_state.login_choice = "teacher"

    if st.session_state.login_choice == "coordinator":
        code = st.text_input("קוד גישה", type="password")
        if st.button("כניסה", type="primary"):
            if code == COORDINATOR_CODE:
                st.session_state.role = "coordinator"
                st.rerun()
            else:
                st.error("קוד גישה שגוי")

    elif st.session_state.login_choice == "teacher":
        code = st.text_input("קוד זיהוי אישי", type="password")
        if st.button("כניסה", type="primary"):
            teacher = session.execute(select(Teacher).where(Teacher.code == code)).scalars().first()
            if teacher:
                st.session_state.role = "teacher"
                st.session_state.teacher_name = teacher.name
                st.rerun()
            else:
                st.error("קוד לא נמצא - בדוק/י מול הרכז/ת")

    session.close()
    st.stop()

# ---------- ניווט ----------
if st.session_state.role == "coordinator":
    st.sidebar.title("📋 ניהול משימות שכבה")
    page = st.sidebar.radio(
        "בחר מסך",
        [
            "➕ הוספת משימה", "✅ תור בדיקה", "📑 כל המשימות",
            "👩‍🏫 תצוגת מחנכים", "🔑 ניהול קודי מחנכים", "⚙️ תבניות וחוקים",
        ],
    )
else:
    st.sidebar.title(f"שלום, {st.session_state.teacher_name}")
    page = "👩‍🏫 תצוגת מחנכים"

st.sidebar.caption(APP_VERSION)
if st.sidebar.button("התנתקות"):
    st.session_state.role = None
    st.session_state.pop("teacher_name", None)
    st.rerun()

# ============================================================
# מסך 1: הוספת משימה
# ============================================================
if page == "➕ הוספת משימה":
    st.header("הוספת משימה חדשה")
    st.caption("כתוב את המשימה במשפט חופשי - המערכת תנסה לזהות למי מיועד, תאריך יעד ודחיפות. "
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
            new_deadline = col3.date_input("תאריך יעד", value=default_deadline, key=f"deadline_{task.id}")
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
# מסך 3: כל המשימות - רכז/ת בלבד, עם עריכת סטטוס
# ============================================================
elif page == "📑 כל המשימות":
    st.header("כל המשימות")
    status_filter = st.multiselect("סינון לפי סטטוס", ALL_STATUSES, default=ALL_STATUSES)
    query = select(Task).order_by(Task.urgent.desc(), Task.deadline.is_(None), Task.deadline)
    tasks = session.execute(query).scalars().all()
    tasks = [t for t in tasks if t.status in status_filter]

    st.link_button(
        "📤 ייצוא סיכום שבועי לווטסאפ",
        build_wa_link(build_weekly_message(tasks)),
        help="כולל את המשימות המוצגות כרגע עם תאריך יעד ב-7 הימים הקרובים",
    )

    if not tasks:
        st.info("אין משימות להצגה.")

    for task in tasks:
        with st.container(border=True):
            c_badge, c_title, c_assignee, c_deadline, c_status, c_update, c_return, c_wa = st.columns(
                [0.6, 3, 1.6, 1.3, 1.6, 0.6, 0.6, 0.6]
            )
            c_badge.markdown("🔴" if task.urgent else "")
            c_title.markdown(f"**{task.title or task.original_text}**")
            c_assignee.caption(f"👤 {task.assignee}" if task.assignee else "")
            c_deadline.caption(f"📅 {task.deadline}" if task.deadline else "")
            c_wa.link_button(
                "📤", build_wa_link(build_task_message(task)), help="שתף משימה זו בווטסאפ"
            )

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
# מסך: תצוגת מחנכים - טבלה ידידותית למובייל, לא ניתנת לעריכה
# ============================================================
elif page == "👩‍🏫 תצוגת מחנכים":
    st.header("תצוגת מחנכים")

    all_tasks = session.execute(
        select(Task).order_by(Task.urgent.desc(), Task.deadline.is_(None), Task.deadline)
    ).scalars().all()

    open_only = st.checkbox("רק משימות פתוחות", value=True)
    assignees = sorted({t.assignee for t in all_tasks if t.assignee})
    options = ["הכל"] + assignees
    default_index = 0
    if st.session_state.role == "teacher":
        teacher_name = st.session_state.teacher_name
        if teacher_name in assignees:
            default_index = options.index(teacher_name)
    selected_assignee = st.selectbox("הצג משימות של", options, index=default_index)

    view_tasks = all_tasks
    if open_only:
        view_tasks = [t for t in view_tasks if t.status != STATUS_CLOSED]
    if selected_assignee != "הכל":
        view_tasks = [t for t in view_tasks if t.assignee == selected_assignee]

    if not view_tasks:
        st.info("אין משימות להצגה.")
    else:
        st.dataframe(
            [
                {
                    "כותרת": t.title or t.original_text,
                    "למי מיועד": t.assignee or "",
                    "תאריך יעד": t.deadline or "",
                    "דחוף": "🔴" if t.urgent else "",
                    "סטטוס": t.status,
                }
                for t in view_tasks
            ],
            column_order=["סטטוס", "דחוף", "תאריך יעד", "למי מיועד", "כותרת"],
            hide_index=True,
            use_container_width=True,
        )

# ============================================================
# מסך: ניהול קודי מחנכים - רכז/ת בלבד
# ============================================================
elif page == "🔑 ניהול קודי מחנכים":
    st.header("ניהול קודי מחנכים")
    st.caption("כל מחנך/ת מקבל/ת קוד אישי לכניסה למסך 'תצוגת מחנכים'. "
               "הקוד לא מוצפן - זו דלת נעולה פשוטה, לא אבטחה אמיתית.")

    with st.form("add_teacher"):
        col1, col2 = st.columns(2)
        name = col1.text_input("שם המחנך/ת")
        code = col2.text_input("קוד זיהוי")
        submitted = st.form_submit_button("הוסף מחנך/ת")
        if submitted and name and code:
            existing = session.execute(select(Teacher).where(Teacher.code == code)).scalars().first()
            if existing:
                st.error("קוד זה כבר קיים - בחר/י קוד אחר")
            else:
                session.add(Teacher(name=name, code=code))
                session.commit()
                st.success("המחנך/ת נוסף/ה")
                st.rerun()

    st.subheader("מחנכים קיימים")
    teachers = session.execute(select(Teacher)).scalars().all()
    if not teachers:
        st.info("עדיין לא הוגדרו מחנכים.")
    else:
        h1, h2, h3 = st.columns([3, 3, 1])
        h1.markdown("**שם**")
        h2.markdown("**קוד**")
    for t in teachers:
        c1, c2, c3 = st.columns([3, 3, 1])
        c1.write(t.name)
        c2.write(t.code)
        if c3.button("מחק", key=f"delteacher_{t.id}"):
            session.delete(t)
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
