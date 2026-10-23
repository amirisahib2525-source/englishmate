"""EnglishMate - English learning app for Dari speakers.

Vocabulary, quizzes, mistakes and progress work WITHOUT any AI key.
The AI teacher is optional and needs GEMINI_API_KEY (Streamlit Secrets or env var).
"""
import html
import os
import random
import re
import sqlite3
import threading
import time

import requests
import streamlit as st

DB_PATH = os.environ.get("ENGLISHMATE_DB", "englishmate.db")
DEFAULT_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
DB_LOCK = threading.Lock()

PAGES = ["🏠 خانه", "📖 لغات", "📝 کویز", "👩‍🏫 معلم AI", "📊 پیشرفت"]
PAGE_HOME, PAGE_VOCAB, PAGE_QUIZ, PAGE_AI, PAGE_PROGRESS = PAGES
MODE_LABELS = {"vocab": "لغات", "grammar": "گرامر", "mixed": "ترکیبی"}

# ----------------------------------------------------------------- content
# (English, Dari, example sentence, category)
WORDS = [
    ("mother", "مادر", "My mother is at home.", "فامیل"),
    ("father", "پدر", "My father works in a shop.", "فامیل"),
    ("brother", "برادر", "My brother is a student.", "فامیل"),
    ("sister", "خواهر", "My sister likes books.", "فامیل"),
    ("friend", "دوست", "He is my friend.", "فامیل"),
    ("family", "فامیل", "I love my family.", "فامیل"),
    ("bread", "نان", "I eat bread in the morning.", "غذا"),
    ("tea", "چای", "She drinks tea every day.", "غذا"),
    ("water", "آب", "Please give me some water.", "غذا"),
    ("apple", "سیب", "This apple is sweet.", "غذا"),
    ("food", "غذا", "The food is ready.", "غذا"),
    ("school", "مکتب", "I go to school every day.", "مکتب و کار"),
    ("teacher", "معلم", "The teacher is kind.", "مکتب و کار"),
    ("student", "شاگرد", "She is a good student.", "مکتب و کار"),
    ("book", "کتاب", "I read a book at night.", "مکتب و کار"),
    ("work", "کار", "I have work today.", "مکتب و کار"),
    ("doctor", "داکتر", "The doctor helps sick people.", "مکتب و کار"),
    ("hospital", "شفاخانه", "The hospital is near my house.", "مکتب و کار"),
    ("money", "پول", "I need some money.", "مکتب و کار"),
    ("house", "خانه", "Our house is small.", "شهر و اشیا"),
    ("city", "شهر", "Kabul is a big city.", "شهر و اشیا"),
    ("road", "سرک", "The road is long.", "شهر و اشیا"),
    ("market", "بازار", "I go to the market on Friday.", "شهر و اشیا"),
    ("door", "دروازه", "Close the door, please.", "شهر و اشیا"),
    ("window", "کلکین", "Open the window, please.", "شهر و اشیا"),
    ("car", "موتر", "He has a new car.", "شهر و اشیا"),
    ("sun", "آفتاب", "The sun is hot.", "طبیعت و وقت"),
    ("rain", "باران", "I like the rain.", "طبیعت و وقت"),
    ("morning", "صبح", "Good morning!", "طبیعت و وقت"),
    ("night", "شب", "Good night.", "طبیعت و وقت"),
    ("day", "روز", "Today is a good day.", "طبیعت و وقت"),
    ("time", "وقت", "What time is it?", "طبیعت و وقت"),
    ("year", "سال", "This year I study English.", "طبیعت و وقت"),
    ("big", "بزرگ", "It is a big house.", "صفت‌ها"),
    ("small", "کوچک", "I have a small bag.", "صفت‌ها"),
    ("good", "خوب", "This is a good book.", "صفت‌ها"),
    ("bad", "بد", "The weather is bad.", "صفت‌ها"),
    ("new", "نو", "I have a new phone.", "صفت‌ها"),
    ("old", "کهنه", "This is an old car.", "صفت‌ها"),
    ("hot", "گرم", "The tea is hot.", "صفت‌ها"),
    ("cold", "سرد", "The water is cold.", "صفت‌ها"),
    ("learn", "یاد گرفتن", "I learn English.", "فعل‌ها"),
    ("write", "نوشتن", "I write a letter.", "فعل‌ها"),
    ("read", "خواندن", "I read every night.", "فعل‌ها"),
    ("eat", "خوردن", "We eat lunch at noon.", "فعل‌ها"),
    ("drink", "نوشیدن", "I drink water.", "فعل‌ها"),
    ("go", "رفتن", "I go to school.", "فعل‌ها"),
    ("come", "آمدن", "Please come here.", "فعل‌ها"),
    ("see", "دیدن", "I see a bird.", "فعل‌ها"),
    ("help", "کمک کردن", "Can you help me?", "فعل‌ها"),
]
WORD_BY_EN = {w[0]: w for w in WORDS}
CATEGORIES = sorted({w[3] for w in WORDS})

# (sentence with ___, options, correct option, explanation in Dari)
GRAMMAR = [
    ("She ___ to school every day.", ["go", "goes", "going", "gone"], "goes",
     "در زمان حال ساده، با she / he / it به آخر فعل s یا es اضافه میشود: goes."),
    ("I ___ a student.", ["is", "are", "am", "be"], "am",
     "با I همیشه از am استفاده میشود."),
    ("They ___ playing football now.", ["is", "am", "are", "be"], "are",
     "با they از are استفاده میشود. کلمهٔ now نشان میدهد کار در حال انجام است."),
    ("He ___ not like tea.", ["do", "does", "is", "are"], "does",
     "در منفی زمان حال ساده، با he / she / it از does not استفاده میشود."),
    ("We ___ to the market yesterday.", ["go", "goes", "went", "going"], "went",
     "کلمهٔ yesterday یعنی گذشته. گذشتهٔ go میشود went."),
    ("There ___ a book on the table.", ["is", "are", "am", "were"], "is",
     "برای یک چیز (مفرد) از there is استفاده میشود."),
    ("I have ___ apple.", ["a", "an", "the", "two"], "an",
     "قبل از کلماتی که با صدای مصوت شروع میشوند (a, e, i, o, u) از an استفاده میشود."),
    ("She is ___ than her sister.", ["tall", "taller", "tallest", "more tall"], "taller",
     "برای مقایسهٔ دو نفر، به آخر صفت کوتاه er اضافه میشود: taller than."),
    ("___ you speak English?", ["Do", "Does", "Is", "Are"], "Do",
     "در سوال زمان حال ساده با you و I و we و they از Do استفاده میشود."),
    ("I ___ breakfast at seven o'clock.", ["has", "have", "having", "haves"], "have",
     "با I از have استفاده میشود (has فقط با he / she / it)."),
    ("My brother ___ in Kabul.", ["live", "lives", "living", "lived"], "lives",
     "مفرد سوم شخص (my brother = he) در زمان حال ساده s میگیرد: lives."),
    ("He ___ my friend.", ["are", "am", "is", "be"], "is",
     "با he / she / it از is استفاده میشود."),
]


# ----------------------------------------------------------------- database
SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student TEXT, topic TEXT, score INTEGER, total INTEGER,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS wrong_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student TEXT, topic TEXT, question TEXT, wrong_answer TEXT, correct_answer TEXT,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vocab_status (
    student TEXT, word TEXT, known INTEGER,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student, word)
);
"""


@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


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


# ----------------------------------------------------------------- quiz logic
def vocab_question(word):
    en, fa, example, _cat = word
    explain = f"«{en}» یعنی «{fa}». مثال: {example}"
    if random.random() < 0.5:
        pool = [w[1] for w in WORDS if w[1] != fa]
        opts = random.sample(pool, 3) + [fa]
        random.shuffle(opts)
        return {"key": f"v:{en}:en2fa", "q": f"What does “{en}” mean?", "qdir": "ltr",
                "options": opts, "odir": "rtl", "answer": opts.index(fa), "explain": explain}
    pool = [w[0] for w in WORDS if w[0] != en]
    opts = random.sample(pool, 3) + [en]
    random.shuffle(opts)
    return {"key": f"v:{en}:fa2en", "q": f"«{fa}» به انگلیسی چه میشود؟", "qdir": "rtl",
            "options": opts, "odir": "ltr", "answer": opts.index(en), "explain": explain}


def grammar_question(item):
    sentence, options, correct, explain = item
    opts = list(options)
    random.shuffle(opts)
    return {"key": f"g:{sentence}", "q": sentence, "qdir": "ltr", "options": opts,
            "odir": "ltr", "answer": opts.index(correct),
            "explain": f"جملهٔ درست: {sentence.replace('___', correct)} — {explain}"}


def build_questions(mode, n, avoid_key=None):
    """n unique questions. First question never equals avoid_key."""
    pool = []
    if mode in ("vocab", "mixed"):
        pool += [vocab_question(w) for w in WORDS]
    if mode in ("grammar", "mixed"):
        pool += [grammar_question(g) for g in GRAMMAR]
    random.shuffle(pool)
    n = max(1, min(n, len(pool)))
    questions = pool[:n]
    if avoid_key and questions[0]["key"] == avoid_key and len(pool) > n:
        questions[0] = pool[n]
    elif avoid_key and questions[0]["key"] == avoid_key and n > 1:
        questions[0], questions[1] = questions[1], questions[0]
    return questions


def start_quiz(student, mode, n):
    questions = build_questions(mode, n, st.session_state.get("last_quiz_key"))
    st.session_state.quiz = {
        "id": random.randint(1, 10**9), "student": student, "mode": mode,
        "questions": questions, "pos": 0, "answered": False, "picked": None,
        "score": 0, "log": [], "finished": False, "saved": False,
    }


def start_quiz_cb():
    start_quiz(
        current_student(),
        st.session_state.get("quiz_mode", "mixed"),
        int(st.session_state.get("quiz_n", 10)),
    )


def _save_result(qz):
    if qz["saved"]:
        return
    qz["saved"] = True
    q_run(
        "INSERT INTO exam_results (student, topic, score, total) VALUES (?,?,?,?)",
        (qz["student"], "کویز " + MODE_LABELS[qz["mode"]], qz["score"], len(qz["questions"])),
    )
    st.session_state.last_quiz_key = qz["questions"][-1]["key"]


def answer_quiz(i):
    """Each question can be answered exactly once (guarded by qz['answered'])."""
    qz = st.session_state.get("quiz")
    if not qz or qz["finished"] or qz["answered"]:
        return
    q = qz["questions"][qz["pos"]]
    if not 0 <= i < len(q["options"]):
        return
    qz["answered"] = True
    qz["picked"] = i
    ok = i == q["answer"]
    picked, correct = q["options"][i], q["options"][q["answer"]]
    qz["log"].append({"q": q["q"], "qdir": q["qdir"], "picked": picked,
                      "correct": correct, "ok": ok, "explain": q["explain"]})
    if ok:
        qz["score"] += 1
    else:
        q_run(
            "INSERT INTO wrong_answers (student, topic, question, wrong_answer, correct_answer) "
            "VALUES (?,?,?,?,?)",
            (qz["student"], "کویز " + MODE_LABELS[qz["mode"]], q["q"], picked, correct),
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


# ----------------------------------------------------------------- flashcards
def start_flash(student, only_review):
    if only_review:
        status = dict(q_all("SELECT word, known FROM vocab_status WHERE student=?", (student,)))
        words = [w[0] for w in WORDS if status.get(w[0]) == 0]
    else:
        words = [w[0] for w in WORDS]
    random.shuffle(words)
    st.session_state.flash = {"student": student, "words": words, "pos": 0,
                              "show": False, "known": 0, "review": 0}


def start_flash_cb():
    start_flash(current_student(), bool(st.session_state.get("flash_only", False)))


def flash_show():
    f = st.session_state.get("flash")
    if f and f["pos"] < len(f["words"]):
        f["show"] = True


def flash_mark(is_known):
    f = st.session_state.get("flash")
    if not f or f["pos"] >= len(f["words"]) or not f["show"]:
        return
    word = f["words"][f["pos"]]
    q_run(
        "INSERT OR REPLACE INTO vocab_status (student, word, known, updated) "
        "VALUES (?,?,?,CURRENT_TIMESTAMP)",
        (f["student"], word, 1 if is_known else 0),
    )
    f["known" if is_known else "review"] += 1
    f["pos"] += 1
    f["show"] = False


def reset_flash():
    st.session_state.pop("flash", None)


# ----------------------------------------------------------------- stats
def get_stats(student):
    res = q_all("SELECT score, total FROM exam_results WHERE student=?", (student,))
    pcts = [r[0] * 100 / r[1] for r in res if r[1]]
    mistakes = q_all("SELECT COUNT(*) FROM wrong_answers WHERE student=?", (student,))[0][0]
    vs = q_all("SELECT known, COUNT(*) FROM vocab_status WHERE student=? GROUP BY known", (student,))
    counts = {k: c for k, c in vs}
    return {
        "quizzes": len(res),
        "avg": sum(pcts) / len(pcts) if pcts else None,
        "best": max(pcts) if pcts else None,
        "mistakes": mistakes,
        "known": counts.get(1, 0),
        "review": counts.get(0, 0),
    }


# ----------------------------------------------------------------- AI
def get_secret(name):
    try:
        value = st.secrets[name]
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(name) or None


def ai_available():
    return bool(get_secret("GEMINI_API_KEY"))


def ask_ai(history, system_text):
    """Returns (text, error). Retries busy models, then tries the next model."""
    key = get_secret("GEMINI_API_KEY")
    if not key:
        return None, "NO_KEY"
    models = []
    custom = get_secret("GEMINI_MODEL")
    if custom:
        models.append(custom)
    models += [m for m in DEFAULT_MODELS if m not in models]
    body = {
        "system_instruction": {"parts": [{"text": system_text}]},
        "contents": [{"role": m["role"], "parts": [{"text": m["text"]}]} for m in history],
    }
    last_err = "unknown error"
    for model in models:
        for _attempt in range(2):
            try:
                r = requests.post(API_URL.format(model), headers={"x-goog-api-key": key},
                                  json=body, timeout=60)
                data = r.json()
            except Exception as e:
                last_err = f"connection: {e}"
                time.sleep(1)
                continue
            if "candidates" in data:
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"], None
                except (KeyError, IndexError):
                    last_err = "empty answer"
                    break
            err = data.get("error", {})
            last_err = err.get("message", last_err)
            if err.get("code") in (429, 500, 502, 503, 504):
                time.sleep(1.5)
                continue
            break
    return None, last_err


def friendly_error(err):
    low = (err or "").lower()
    if err == "NO_KEY":
        return "معلم AI تنظیم نشده است."
    if "demand" in low or "overload" in low or "unavailable" in low or "quota" in low:
        return "مدل AI در این لحظه شلوغ است. چند دقیقه بعد دوباره امتحان کو."
    return f"خطا از سرویس AI: {err}"


def teacher_prompt(level):
    return (
        "You are a kind, patient English teacher for Afghan students who speak Dari. "
        f"Student level: {level}. Explain in simple English AND in simple Dari. "
        "Keep answers short and well organised for a phone screen. Use Markdown."
    )


def split_practice(text):
    parts = re.split(r"-{3}\s*ANSWERS\s*-{3}", text, maxsplit=1, flags=re.I)
    questions = parts[0].strip()
    answers = parts[1].strip() if len(parts) > 1 else ""
    return questions, answers


# ----------------------------------------------------------------- UI helpers
CSS = """
<style>
:root {--navy:#0b1f4d; --blue:#2563eb; --light:#eaf1ff; --line:#d6e2ff;}
.block-container {max-width: 760px; padding-top: 1rem; padding-bottom: 4rem;}
[data-testid="stMain"] .block-container {direction: rtl; text-align: right;}
.hero {background: linear-gradient(135deg, #0b1f4d 0%, #2563eb 100%); color: #fff;
       border-radius: 18px; padding: 18px 16px; text-align: center; margin-bottom: 12px;}
.hero h1 {color:#fff; margin:0; font-size:1.7rem;}
.hero p {color:#dbe7ff; margin:4px 0 0 0;}
.card {background:#fff; color:var(--navy); border:1px solid var(--line);
       border-radius:14px; padding:12px 14px; margin:8px 0;}
.card.ok {border-right:6px solid #2e9e5b;}
.card.bad {border-right:6px solid #d64545;}
.card.q {background:var(--light); font-size:1.15rem; font-weight:600;}
.ltr {direction:ltr; text-align:left;}
.rtl {direction:rtl; text-align:right;}
.opt {background:#fff; color:var(--navy); border:1.5px solid var(--line);
      border-radius:12px; padding:10px 14px; margin:6px 0;}
.opt.right {background:#e7f8ee; border-color:#2e9e5b;}
.opt.wrong {background:#fdecec; border-color:#d64545;}
.word {font-size:1.25rem; font-weight:700;}
.mean {color:var(--blue); font-weight:600;}
.ex {color:#51608a; font-size:.95rem;}
.score {font-size:2.8rem; font-weight:800; text-align:center; color:var(--blue); margin:0;}
.stButton > button {width:100%; border-radius:12px; font-weight:600;}
div[role="radiogroup"] {gap:.4rem; flex-wrap:wrap;}
</style>
"""


def esc(x):
    return html.escape(str(x))


def goto(page):
    st.session_state["nav"] = page


def page_home(student):
    stats = get_stats(student)
    st.markdown(f"### سلام {esc(student)} 👋")
    st.write("با EnglishMate لغات و گرامر انگلیسی را قدم‌به‌قدم یاد بگیر.")
    c1, c2 = st.columns(2)
    c1.metric("کویزهای داده‌شده", stats["quizzes"])
    c2.metric("اوسط نمره", "—" if stats["avg"] is None else f"{stats['avg']:.0f}٪")
    st.button("📖 لغات و کارت‌ها", on_click=goto, args=(PAGE_VOCAB,), key="h_vocab")
    st.button("📝 شروع کویز", on_click=goto, args=(PAGE_QUIZ,), key="h_quiz")
    st.button("👩‍🏫 معلم AI", on_click=goto, args=(PAGE_AI,), key="h_ai")
    if ai_available():
        st.success("معلم AI فعال است.")
    else:
        st.info("لغات، کویز و پیشرفت بدون AI کار میکنند. معلم AI نیاز به تنظیم کلید دارد.")


def page_vocab(student):
    t_list, t_cards = st.tabs(["📚 فهرست لغات", "🃏 تمرین با کارت"])
    with t_list:
        c1, c2 = st.columns(2)
        search = c1.text_input("🔎 جستجو").strip().lower()
        cat = c2.selectbox("دسته", ["همه"] + CATEGORIES)
        shown = [
            w for w in WORDS
            if (cat == "همه" or w[3] == cat) and (not search or search in w[0] or search in w[1])
        ]
        st.caption(f"{len(shown)} لغت")
        for en, fa, ex, _c in shown:
            st.markdown(
                f'<div class="card"><div class="word ltr">{esc(en)}</div>'
                f'<div class="mean">{esc(fa)}</div>'
                f'<div class="ex ltr">{esc(ex)}</div></div>',
                unsafe_allow_html=True,
            )
    with t_cards:
        f = st.session_state.get("flash")
        if not f:
            st.write("لغت را ببین، معنی را به یاد بیاور، بعد معنی را چک کو.")
            st.checkbox("فقط لغاتی که باید مرور کنم", key="flash_only")
            st.button("🚀 شروع تمرین", on_click=start_flash_cb, key="flash_start")
        elif not f["words"]:
            st.info("لغتی برای مرور نیست. اول تمرین عادی را انجام بده.")
            st.button("برگشت", on_click=reset_flash, key="flash_back")
        elif f["pos"] >= len(f["words"]):
            st.success(f"تمرین تمام شد. بلد بودم: {f['known']} | باید مرور کنم: {f['review']}")
            st.button("🔄 تمرین دوباره", on_click=reset_flash, key="flash_again")
        else:
            en, fa, ex, _c = WORD_BY_EN[f["words"][f["pos"]]]
            st.progress(f["pos"] / len(f["words"]))
            st.caption(f"کارت {f['pos'] + 1} از {len(f['words'])}")
            body = f'<div class="word ltr" style="font-size:2rem">{esc(en)}</div>'
            if f["show"]:
                body += f'<div class="mean">{esc(fa)}</div><div class="ex ltr">{esc(ex)}</div>'
            st.markdown(f'<div class="card">{body}</div>', unsafe_allow_html=True)
            if not f["show"]:
                st.button("👀 معنی را نشان بده", on_click=flash_show, key=f"fs_{f['pos']}")
            else:
                st.button("✅ بلد بودم", on_click=flash_mark, args=(True,), key=f"fk_{f['pos']}")
                st.button("🔁 باید مرور کنم", on_click=flash_mark, args=(False,), key=f"fr_{f['pos']}")

def page_quiz(student):
    qz = st.session_state.get("quiz")
    if not qz:
        st.subheader("کویز جدید")
    st.radio("نوع کویز", list(MODE_LABELS), format_func=MODE_LABELS.get, key="quiz_mode", horizontal=True, index=2)
