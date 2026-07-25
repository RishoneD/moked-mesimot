"""
שכבת גישה לבסיס הנתונים.
מקומית: SQLite (קובץ tasks.db).
בפרודקשן: קבע משתנה סביבה DATABASE_URL לכתובת Supabase (Postgres) —
לא צריך לשנות שורת קוד נוספת, SQLAlchemy מטפל בהבדל בין הדיאלקטים.
"""
import os
import datetime as dt
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, DateTime, Text, select
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tasks.db")

# Supabase/Postgres connection strings לפעמים מגיעות בפורמט postgres:// הישן —
# SQLAlchemy מצפה ל-postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

STATUS_PENDING = "ממתין לאישור"
STATUS_ACTION = "לפעולה"
STATUS_FOLLOWUP = "למעקב"
STATUS_CLOSED = "סגורה"

ALL_STATUSES = [STATUS_PENDING, STATUS_ACTION, STATUS_FOLLOWUP, STATUS_CLOSED]


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False, default="")
    original_text = Column(Text, nullable=False)
    assignee = Column(String(200), nullable=True)
    deadline = Column(String(50), nullable=True)  # נשמר כטקסט (YYYY-MM-DD) לפשטות
    urgent = Column(Boolean, default=False)
    status = Column(String(30), nullable=False, default=STATUS_PENDING)
    coordinator_notes = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class Rule(Base):
    """
    ספריית חוקים/תבניות הניתנת להרחבה - למשל מיפוי כינוי -> שם מלא של מורה.
    כשמנוע הפענוח לא מזהה שדה, הרכז יכול להוסיף כאן כלל חדש כדי שהפעם
    הבאה הביטוי הדומה ייפול נכון אוטומטית.
    """
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True)
    rule_type = Column(String(30), nullable=False)  # "assignee_alias" | "keyword"
    pattern = Column(String(200), nullable=False)     # מה לחפש בטקסט
    value = Column(String(200), nullable=False)        # לאיזה ערך זה ממופה
    created_at = Column(DateTime, default=dt.datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
