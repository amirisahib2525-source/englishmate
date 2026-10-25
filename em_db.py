"""EnglishMate database helpers (SQLite)."""
import os
import sqlite3
import tempfile
import threading

import streamlit as st

DB_PATH = os.environ.get("ENGLISHMATE_DB", "englishmate.db")
DB_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student TEXT, topic TEXT, score INTEGER, total INTEGER,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS wrong_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student TEXT, topic TEXT, question TEXT,
    wrong_answer TEXT, correct_answer TEXT,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS word_progress (
    student TEXT, wid TEXT, status TEXT,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student, wid)
);
"""


def _open(path):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


@st.cache_resource
def get_conn():
    try:
        return _open(DB_PATH)
    except (sqlite3.Error, OSError):
        # The project folder may be read-only: use a temporary file.
        return _open(os.path.join(tempfile.gettempdir(), "englishmate.db"))


def q_all(sql, params=()):
    with DB_LOCK:
        return get_conn().execute(sql, params).fetchall()


def q_run(sql, params=()):
    with DB_LOCK:
        conn = get_conn()
        conn.execute(sql, params)
        conn.commit()


def current_student():
    name = (st.session_state.get("student_input") or "").strip()
    return name or "مهمان"


def display_name():
    """Name shown in the greeting. Friendly text when no name is typed."""
    name = (st.session_state.get("student_input") or "").strip()
    return name or "دوست خوبم"


def current_level():
    return st.session_state.get("level", "beginner")


# ----------------------------------------------------------- word progress
def set_word_status(student, wid, status):
    """status: 'learned', 'difficult' or None (remove)."""
    if status is None:
        q_run("DELETE FROM word_progress WHERE student=? AND wid=?",
              (student, wid))
        return
    q_run(
        "INSERT OR REPLACE INTO word_progress (student, wid, status, updated) "
        "VALUES (?,?,?,CURRENT_TIMESTAMP)",
        (student, wid, status),
    )


def word_status_map(student):
    rows = q_all("SELECT wid, status FROM word_progress WHERE student=?",
                 (student,))
    return dict(rows)


# ----------------------------------------------------------- stats
def get_stats(student):
    res = q_all(
        "SELECT score, total FROM exam_results WHERE student=?", (student,)
    )
    pcts = [r[0] * 100 / r[1] for r in res if r[1]]
    mistakes = q_all(
        "SELECT COUNT(*) FROM wrong_answers WHERE student=?", (student,)
    )[0][0]
    counts = dict(q_all(
        "SELECT status, COUNT(*) FROM word_progress "
        "WHERE student=? GROUP BY status",
        (student,),
    ))
    return {
        "quizzes": len(res),
        "avg": sum(pcts) / len(pcts) if pcts else None,
        "best": max(pcts) if pcts else None,
        "mistakes": mistakes,
        "learned": counts.get("learned", 0),
        "difficult": counts.get("difficult", 0),
    }
