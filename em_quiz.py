"""EnglishMate quiz logic (vocabulary + grammar) as a small state machine.

State lives in st.session_state['quiz']. Every change happens inside
callbacks, so a question can only be answered once.
"""
import random

import streamlit as st

from em_content import LEVELS, load_grammar, words_for
from em_db import current_level, current_student, q_run

MODE_LABELS = {"vocab": "لغات", "grammar": "گرامر", "mixed": "ترکیبی"}
KINDS = {
    "beginner": ["en2fa", "fa2en"],
    "intermediate": ["en2fa", "fa2en", "def2en"],
    "advanced": ["def2en", "cloze", "fa2en"],
}


def _distractors(pool, field, correct, k=3):
    seen, out = {correct}, []
    items = pool[:]
    random.shuffle(items)
    for w in items:
        text = w[field]
        if text not in seen:
            seen.add(text)
            out.append(text)
        if len(out) == k:
            break
    return out


def _explain(w):
    return (f"«{w['w']}» یعنی «{w['fa']}». {w['def']} "
            f"مثال: {w['ex']} — {w['exfa']}")


def vocab_question(w, pool):
    kind = random.choice(KINDS[w["level"]])
    if kind == "cloze" and w["w"].lower() not in w["ex"].lower():
        kind = "def2en"
    if kind == "en2fa":
        q, field, correct = f"What does “{w['w']}” mean?", "fa", w["fa"]
        qdir, odir = "ltr", "rtl"
    elif kind == "fa2en":
        q, field, correct = f"«{w['fa']}» به انگلیسی چه میشود؟", "w", w["w"]
        qdir, odir = "rtl", "ltr"
    elif kind == "def2en":
        q, field, correct = f"Which word means: {w['def']}", "w", w["w"]
        qdir, odir = "ltr", "ltr"
    else:
        blank = _blank(w["ex"], w["w"])
        q, field, correct = f"Complete: {blank}", "w", w["w"]
        qdir, odir = "ltr", "ltr"
    opts = _distractors(pool, field, correct) + [correct]
    random.shuffle(opts)
    return {
        "key": f"v:{w['id']}:{kind}", "q": q, "qdir": qdir,
        "options": opts, "odir": odir, "answer": opts.index(correct),
        "explain": _explain(w),
    }


def _blank(sentence, word):
    low = sentence.lower()
    i = low.find(word.lower())
    return sentence[:i] + "_____" + sentence[i + len(word):]


def grammar_questions(tense_id=None):
    out = []
    for lesson in load_grammar()[0]:
        if tense_id and lesson["id"] != tense_id:
            continue
        for idx, m in enumerate(lesson["mcq"]):
            opts = list(m["options"])
            random.shuffle(opts)
            out.append({
                "key": f"g:{lesson['id']}:{idx}", "q": m["q"],
                "qdir": "ltr", "options": opts, "odir": "ltr",
                "answer": opts.index(m["answer"]),
                "explain": f"{lesson['en']} — {m['explain']}",
            })
    return out


def build_questions(mode, n, level, tense_id=None, avoid_key=None):
    """n unique questions. The first one never equals avoid_key."""
    pool = []
    if mode in ("vocab", "mixed"):
        words = words_for(level)
        pool += [vocab_question(w, words) for w in words]
    if mode in ("grammar", "mixed"):
        pool += grammar_questions(tense_id)
    random.shuffle(pool)
    if not pool:
        return []
    n = max(1, min(n, len(pool)))
    questions = pool[:n]
    if avoid_key and questions[0]["key"] == avoid_key:
        if len(pool) > n:
            questions[0] = pool[n]
        elif n > 1:
            questions[0], questions[1] = questions[1], questions[0]
    return questions


def quiz_label(mode, level):
    base = "کویز " + MODE_LABELS[mode]
    if mode != "grammar":
        base += f" ({LEVELS[level]})"
    return base


def start_quiz(student, mode, n, level, tense_id=None):
    last = st.session_state.get("last_quiz_key")
    questions = build_questions(mode, n, level, tense_id, last)
    if not questions:
        st.session_state["quiz_error"] = "سوالی پیدا نشد."
        return
    st.session_state.pop("quiz_error", None)
    st.session_state.quiz = {
        "id": random.randint(1, 10**9), "student": student, "mode": mode,
        "label": quiz_label(mode, level), "questions": questions,
        "pos": 0, "answered": False, "picked": None, "score": 0,
        "log": [], "finished": False, "saved": False,
    }


def start_quiz_cb():
    ss = st.session_state
    mode = ss.get("quiz_mode", "mixed")
    tense = ss.get("quiz_tense") or None
    if tense == "all":
        tense = None
    start_quiz(current_student(), mode, int(ss.get("quiz_n", 10)),
               current_level(), tense)


def _save_result(qz):
    if qz["saved"]:
        return
    qz["saved"] = True
    q_run(
        "INSERT INTO exam_results (student, topic, score, total) "
        "VALUES (?,?,?,?)",
        (qz["student"], qz["label"], qz["score"], len(qz["questions"])),
    )
    st.session_state.last_quiz_key = qz["questions"][-1]["key"]


def answer_quiz(i):
    """A question can be answered exactly once (guard: qz['answered'])."""
    qz = st.session_state.get("quiz")
    if not qz or qz["finished"] or qz["answered"]:
        return
    q = qz["questions"][qz["pos"]]
    if not 0 <= i < len(q["options"]):
        return
    qz["answered"] = True
    qz["picked"] = i
    ok = i == q["answer"]
    picked = q["options"][i]
    correct = q["options"][q["answer"]]
    qz["log"].append({
        "q": q["q"], "qdir": q["qdir"], "picked": picked,
        "correct": correct, "ok": ok, "explain": q["explain"],
    })
    if ok:
        qz["score"] += 1
    else:
        q_run(
            "INSERT INTO wrong_answers "
            "(student, topic, question, wrong_answer, correct_answer) "
            "VALUES (?,?,?,?,?)",
            (qz["student"], qz["label"], q["q"], picked, correct),
        )
    if qz["pos"] == len(qz["questions"]) - 1:
        _save_result(qz)


def next_quiz():
    qz = st.session_state.get("quiz")
    if not qz or qz["finished"] or not qz["answered"]:
        return
    if qz["pos"] + 1 >= len(qz["questions"]):
        _save_result(qz)
        qz["finished"] = True
    else:
        qz["pos"] += 1
        qz["answered"] = False
        qz["picked"] = None


def reset_quiz():
    st.session_state.pop("quiz", None)
