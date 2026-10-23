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
        st.radio("نوع کویز", list(MODE_LABELS), format_func=MODE_LABELS.get,
                 key="quiz_mode", horizontal=True, index=2)
        st.radio("تعداد سوال", [5, 10], key="quiz_n", horizontal=True, index=1)
        st.button("🚀 شروع کویز", on_click=start_quiz_cb, key="quiz_start")
        return
    if qz["finished"]:
        show_quiz_result(qz)
        return

    total, pos = len(qz["questions"]), qz["pos"]
    q = qz["questions"][pos]
    st.progress((pos + (1 if qz["answered"] else 0)) / total)
    st.caption(f"سوال {pos + 1} از {total} • نمره تا حالا: {qz['score']}")
    st.markdown(f'<div class="card q {q["qdir"]}">{esc(q["q"])}</div>', unsafe_allow_html=True)

    if not qz["answered"]:
        for i, opt in enumerate(q["options"]):
            st.button(opt, on_click=answer_quiz, args=(i,), key=f"o_{qz['id']}_{pos}_{i}")
    else:
        for i, opt in enumerate(q["options"]):
            cls = "opt " + q["odir"]
            mark = ""
            if i == q["answer"]:
                cls += " right"
                mark = "✔ "
            elif i == qz["picked"]:
                cls += " wrong"
                mark = "✘ "
            st.markdown(f'<div class="{cls}">{mark}{esc(opt)}</div>', unsafe_allow_html=True)
        if qz["picked"] == q["answer"]:
            st.success("✅ درست!")
        else:
            st.error("❌ غلط. جواب درست با رنگ سبز نشان داده شد.")
        st.info(q["explain"])
        last = pos + 1 >= total
        st.button("🏁 دیدن نتیجه" if last else "➡️ سوال بعدی", on_click=next_quiz,
                  key=f"n_{qz['id']}_{pos}")
    st.button("خروج از کویز", on_click=reset_quiz, key=f"x_{qz['id']}_{pos}")


def show_quiz_result(qz):
    total, score = len(qz["questions"]), qz["score"]
    pct = score * 100 // total
    st.markdown(f'<p class="score">{score} / {total}</p>', unsafe_allow_html=True)
    st.progress(score / total)
    if pct >= 90:
        st.success(f"{pct}٪ — آفرین! عالی بود 🌟")
    elif pct >= 70:
        st.success(f"{pct}٪ — خیلی خوب!")
    elif pct >= 50:
        st.warning(f"{pct}٪ — قابل قبول، کمی تمرین بیشتر.")
    else:
        st.error(f"{pct}٪ — نگران نباش، لغات را مرور کو و دوباره امتحان بده.")
    right = [x for x in qz["log"] if x["ok"]]
    wrong = [x for x in qz["log"] if not x["ok"]]
    st.markdown(f"#### ✅ جواب‌های درست ({len(right)})")
    if not right:
        st.write("—")
    for x in right:
        st.markdown(f'<div class="card ok"><div class="{x["qdir"]}">{esc(x["q"])}</div>'
                    f'<b>✔ {esc(x["correct"])}</b></div>', unsafe_allow_html=True)
    st.markdown(f"#### ❌ جواب‌های غلط ({len(wrong)})")
    if not wrong:
        st.write("هیچ غلطی نداشتی 👏")
    for x in wrong:
        st.markdown(
            f'<div class="card bad"><div class="{x["qdir"]}">{esc(x["q"])}</div>'
            f'جواب تو: <b>{esc(x["picked"])}</b><br>'
            f'جواب درست: <b>{esc(x["correct"])}</b><br>{esc(x["explain"])}</div>',
            unsafe_allow_html=True,
        )
    st.button("🔄 کویز جدید", on_click=reset_quiz, key="quiz_again")
    st.caption("نتیجه و اشتباهات در بخش 📊 پیشرفت ذخیره شد.")


def show_ai_setup():
    st.info(
        "معلم AI برای کار کردن به کلید Gemini نیاز دارد. بدون آن، لغات، کویز و پیشرفت "
        "کار میکنند.\n\n"
        "۱) از aistudio.google.com/apikey کلید رایگان بگیر.\n\n"
        "۲) در Streamlit: Manage app ← Settings ← Secrets و بنویس: "
        "`GEMINI_API_KEY = \"کلید-تو\"`"
    )


def page_ai(student, level):
    st.subheader("👩‍🏫 معلم هوش مصنوعی")
    if not ai_available():
        show_ai_setup()
        return
    tool = st.selectbox("ابزار", ["✍️ تصحیح جمله", "📖 درس کوتاه", "🎯 تمرین از اشتباهاتم",
                                  "💬 پرسش آزاد"])
    system = teacher_prompt(level)

    if tool.startswith("✍️"):
        sentence = st.text_area("جملهٔ انگلیسی‌ات را بنویس", key="ai_sentence")
        if st.button("✍️ تصحیح کو", disabled=not sentence.strip(), key="ai_fix"):
            prompt = (
                f"Student sentence: {sentence}\n"
                "Reply in Markdown with: 1) **Corrected sentence** 2) **Why (simple English)** "
                "3) **چرا (دری ساده)** 4) two new example sentences with Dari translation. "
                "If the sentence is already correct, say so."
            )
            with st.spinner("معلم بررسی میکند..."):
                text, err = ask_ai([{"role": "user", "text": prompt}], system)
            st.session_state["ai_fix_out"] = text or friendly_error(err)
        if st.session_state.get("ai_fix_out"):
            st.markdown(st.session_state["ai_fix_out"])

    elif tool.startswith("📖"):
        topic = st.text_input("موضوع درس", value="Present simple", key="ai_topic")
        if st.button("📖 درس بده", disabled=not topic.strip(), key="ai_lesson"):
            prompt = (f"Give a short lesson about: {topic}. Include the key rule, five examples "
                      "with Dari translation, and one common mistake of Dari speakers. No exercises.")
            with st.spinner("معلم درس را آماده میکند..."):
                text, err = ask_ai([{"role": "user", "text": prompt}], system)
            st.session_state["ai_lesson_out"] = text or friendly_error(err)
        if st.session_state.get("ai_lesson_out"):
            st.markdown(st.session_state["ai_lesson_out"])

    elif tool.startswith("🎯"):
        rows = q_all(
            "SELECT question, wrong_answer, correct_answer FROM wrong_answers "
            "WHERE student=? ORDER BY id DESC LIMIT 10", (student,))
        if not rows:
            st.info("هنوز اشتباهی ذخیره نشده. اول یک کویز بده.")
        elif st.button("🎯 تمرین بساز", key="ai_practice"):
            lines = "\n".join(f"- {a} | my answer: {b} | correct: {c}" for a, b, c in rows)
            prompt = (
                "These are my recent mistakes:\n" + lines +
                "\nWrite 5 NEW multiple-choice practice questions (options A-D) that target "
                "the same weaknesses. Write the questions first. Then write a line containing "
                "exactly ---ANSWERS--- and after it the answers with a short Dari explanation."
            )
            with st.spinner("معلم تمرین میسازد..."):
                text, err = ask_ai([{"role": "user", "text": prompt}], system)
            st.session_state["ai_practice_out"] = text or ("ERR:" + friendly_error(err))
        out = st.session_state.get("ai_practice_out")
        if out:
            if out.startswith("ERR:"):
                st.error(out[4:])
            else:
                questions, answers = split_practice(out)
                st.markdown(questions)
                if answers:
                    with st.expander("✅ جواب‌ها و توضیح"):
                        st.markdown(answers)

    else:
        chat = st.session_state.setdefault("ai_chat", [])
        for m in chat:
            with st.chat_message("user" if m["role"] == "user" else "assistant"):
                st.markdown(m["text"])
        msg = st.chat_input("سوالت را بنویس...")
        if msg:
            chat.append({"role": "user", "text": msg})
            text, err = ask_ai(chat, system)
            chat.append({"role": "model", "text": text or friendly_error(err)})
            st.rerun()


def page_progress(student):
    stats = get_stats(student)
    c1, c2 = st.columns(2)
    c1.metric("کویزها", stats["quizzes"])
    c2.metric("اوسط نمره", "—" if stats["avg"] is None else f"{stats['avg']:.0f}٪")
    c3, c4 = st.columns(2)
    c3.metric("بهترین نمره", "—" if stats["best"] is None else f"{stats['best']:.0f}٪")
    c4.metric("اشتباهات ذخیره‌شده", stats["mistakes"])
    st.caption(f"لغات «بلد بودم»: {stats['known']} • لغات «باید مرور کنم»: {stats['review']}")

    t_scores, t_mistakes = st.tabs(["📈 نمره‌ها", "❌ اشتباهات من"])
    with t_scores:
        rows = q_all("SELECT topic, score, total, created FROM exam_results "
                     "WHERE student=? ORDER BY id", (student,))
        if not rows:
            st.info("هنوز کویزی ندادی.")
        else:
            if len(rows) >= 2:
                st.line_chart([r[1] * 100 / r[2] for r in rows])
                st.caption("نمرهٔ هر کویز (٪)")
            st.dataframe([
                {"نوع": r[0], "نمره": f"{r[1]}/{r[2]}", "درصد": f"{r[1] * 100 // r[2]}٪",
                 "زمان (UTC)": r[3]} for r in reversed(rows[-20:])
            ])
    with t_mistakes:
        rows = q_all("SELECT question, wrong_answer, correct_answer, created FROM wrong_answers "
                     "WHERE student=? ORDER BY id DESC LIMIT 50", (student,))
        if not rows:
            st.success("اشتباهی ذخیره نشده 👏")
        else:
            st.dataframe([{"سوال": a, "جواب تو": b, "جواب درست": c, "زمان (UTC)": d}
                          for a, b, c, d in rows])
    st.caption("توجه: روی Streamlit Community Cloud فایل دیتابیس ممکن است بعد از ری‌استارت پاک شود.")


def main():
    st.set_page_config(page_title="EnglishMate", page_icon="📘", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("nav", PAGES[0])

    st.markdown('<div class="hero"><h1>📘 EnglishMate</h1>'
                "<p>انگلیسی را قدم‌به‌قدم یاد بگیر</p></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.text_input("👤 نام شاگرد", value="مهمان", key="student_input")
    level = c2.selectbox("📶 سطح", ["مبتدی", "متوسط", "پیشرفته"], key="level")
    st.radio("بخش", PAGES, horizontal=True, key="nav", label_visibility="collapsed")

    student, page = current_student(), st.session_state["nav"]
    if page == PAGE_HOME:
        page_home(student)
    elif page == PAGE_VOCAB:
        page_vocab(student)
    elif page == PAGE_QUIZ:
        page_quiz(student)
    elif page == PAGE_AI:
        page_ai(student, level)
    else:
        page_progress(student)


if __name__ == "__main__":
    main() html
import json
import random
import re
import sqlite3

import requests
import streamlit as st

st.set_page_config(page_title="EnglishMate", page_icon="📘", layout="centered")

MODELS = ["gemini-2.5-flash", "gemini-flash-latest"]
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

st.markdown(
    """
<style>
.block-container {max-width: 760px; padding-top: 1.2rem;}
[data-testid="stMain"] .block-container {direction: rtl; text-align: right;}
[data-testid="stRadio"] div[role="radiogroup"] {direction: ltr; text-align: left;}
.card {background: rgba(128,128,128,0.10); border-radius: 14px; padding: 14px 16px;
       margin: 10px 0; border: 1px solid rgba(128,128,128,0.25);}
.ok {border-right: 6px solid #2e9e5b;}
.bad {border-right: 6px solid #d64545;}
.ltr {direction: ltr; text-align: left;}
.score {font-size: 2.6rem; font-weight: 800; text-align: center; margin: 0;}
.hero {text-align: center; padding: 8px 0 4px 0;}
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ database
conn = sqlite3.connect("englishmate.db", check_same_thread=False)
conn.executescript(
    """
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
"""
)
conn.commit()

# ------------------------------------------------------------------ data
TOPICS = [
    "معرفی خود و سلام‌وعلیک (Greetings)",
    "اعضای فامیل (Family)",
    "غذا و نوشیدنی (Food and drinks)",
    "بازار و خرید (Shopping)",
    "اعداد و وقت (Numbers and time)",
    "زمان حال ساده (Present simple)",
    "زمان گذشته ساده (Past simple)",
    "مکتب و دانشگاه (School and university)",
    "کار و شغل (Work and jobs)",
]

WORDS = [
    ("apple", "سیب"), ("book", "کتاب"), ("water", "آب"), ("house", "خانه"),
    ("friend", "دوست"), ("school", "مکتب"), ("teacher", "معلم"),
    ("student", "شاگرد"), ("city", "شهر"), ("food", "غذا"), ("family", "فامیل"),
    ("work", "کار"), ("morning", "صبح"), ("night", "شب"), ("big", "بزرگ"),
    ("small", "کوچک"), ("good", "خوب"), ("bad", "بد"), ("brother", "برادر"),
    ("sister", "خواهر"), ("hand", "دست"), ("eye", "چشم"), ("road", "سرک"),
    ("market", "بازار"), ("bread", "نان"), ("tea", "چای"), ("sun", "آفتاب"),
    ("rain", "باران"), ("learn", "یاد گرفتن"), ("write", "نوشتن"),
]


# ------------------------------------------------------------------ AI helpers
def ask_ai(history, system_text, as_json=False):
    """Returns (text, error). history = [{'role': 'user'|'model', 'text': str}]"""
    try:
        key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None, "کلید Gemini در Secrets گذاشته نشده."
    body = {
        "system_instruction": {"parts": [{"text": system_text}]},
        "contents": [
            {"role": m["role"], "parts": [{"text": m["text"]}]} for m in history
        ],
    }
    if as_json:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    last_err = "خطای نامعلوم"
    for model in MODELS:
        try:
            r = requests.post(
                API_URL.format(model),
                headers={"x-goog-api-key": key},
                json=body,
                timeout=90,
            )
            data = r.json()
            if "candidates" in data:
                return data["candidates"][0]["content"]["parts"][0]["text"], None
            last_err = data.get("error", {}).get("message", last_err)
        except Exception as e:
            last_err = str(e)
    return None, last_err


def teacher_prompt(level):
    return (
        "تو یک معلم مهربان، صبور و حرفه‌ای زبان انگلیسی هستی. شاگرد افغان است و "
        f"دری میداند. سطح شاگرد: {level}. توضیحات را به دری ساده بنویس و مثال‌ها را "
        "به انگلیسی همراه ترجمهٔ دری بیاور. جواب‌ها کوتاه، منظم و مناسب صفحهٔ "
        "مبایل باشند. از Markdown استفاده کو."
    )


def parse_questions(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("questions", [])
    out = []
    for d in data:
        try:
            opts = [str(o) for o in d["options"]]
            idx = int(d["answer_index"])
            if len(opts) != 4 or not 0 <= idx < 4:
                continue
            correct = opts[idx]
            random.shuffle(opts)
            out.append(
                {
                    "q": str(d["q"]),
                    "options": opts,
                    "answer": opts.index(correct),
                    "explain": str(d.get("explain", "")),
                }
            )
        except Exception:
            continue
    return out


def fallback_questions(n=5):
    qs = []
    for en, fa in random.sample(WORDS, n):
        wrong = random.sample([w[1] for w in WORDS if w[1] != fa], 3)
        opts = wrong + [fa]
        random.shuffle(opts)
        qs.append(
            {
                "q": f"What does “{en}” mean?",
                "options": opts,
                "answer": opts.index(fa),
                "explain": f"«{en}» یعنی «{fa}».",
            }
        )
    return qs


def build_exam(topic, level, lesson_text):
    prompt = (
        f"Topic: {topic}\nStudent level: {level}\n"
        "Create exactly 5 multiple-choice English questions for a Dari-speaking "
        "learner. Return ONLY a JSON array. Each item must be: "
        '{"q": "question in English", "options": ["4 short English options"], '
        '"answer_index": 0, "explain": "one short explanation in Dari"}. '
        "Exactly one option is correct. Questions must be clear and different."
    )
    if lesson_text:
        prompt += "\nBase the questions on this lesson:\n" + lesson_text[:1800]
    text, err = ask_ai(
        [{"role": "user", "text": prompt}],
        "You are an English exam writer. Output valid JSON only.",
        as_json=True,
    )
    if text:
        try:
            qs = parse_questions(text)
            if len(qs) >= 3:
                return qs[:5], "ai", None
        except Exception as e:
            err = str(e)
    return fallback_questions(), "fallback", err


# ------------------------------------------------------------------ header
st.markdown(
    '<div class="hero"><h1>📘 EnglishMate</h1>'
    "<p>معلم هوشمند انگلیسی برای شاگردان دری‌زبان</p></div>",
    unsafe_allow_html=True,
)
c1, c2 = st.columns(2)
student = c1.text_input("👤 نام شاگرد", value="مهمان")
level = c2.selectbox("📶 سطح", ["مبتدی", "متوسط", "پیشرفته"])

tab_home, tab_lesson, tab_exam, tab_progress, tab_chat = st.tabs(
    ["🏠 خانه", "📖 درس", "📝 امتحان", "📊 پیشرفت", "💬 معلم"]
)

# ------------------------------------------------------------------ home
with tab_home:
    rows = conn.execute(
        "SELECT score, total FROM exam_results WHERE student=?", (student,)
    ).fetchall()
    m1, m2 = st.columns(2)
    m1.metric("امتحان‌های داده‌شده", len(rows))
    if rows:
        avg = sum(r[0] / r[1] for r in rows) / len(rows) * 100
        m2.metric("اوسط نمره", f"{avg:.0f}٪")
    else:
        m2.metric("اوسط نمره", "—")

    st.markdown(
        """
<div class="card"><b>طرز کار:</b><br>
۱. در تب <b>درس</b> یک موضوع انتخاب کو و درس بگیر.<br>
۲. در تب <b>امتحان</b> امتحان ۵ سوالی بده. جواب‌ها تا آخر نشان داده نمیشوند.<br>
۳. در آخر نمره، جواب‌های درست و غلط و توضیح معلم را میبینی.<br>
۴. در تب <b>پیشرفت</b> رشد خودت را دنبال کو.</div>
""",
        unsafe_allow_html=True,
    )
    try:
        st.secrets["GEMINI_API_KEY"]
    except Exception:
        st.warning("معلم AI هنوز وصل نیست: کلید Gemini را در Secrets بگذار.")

# ------------------------------------------------------------------ lesson
with tab_lesson:
    st.subheader("درس جدید")
    topic_choice = st.selectbox("موضوع درس", TOPICS + ["موضوع دلخواه من"])
    if topic_choice == "موضوع دلخواه من":
        topic = st.text_input("موضوع را بنویس", placeholder="مثلاً: In the hospital")
    else:
        topic = topic_choice

    if st.button("📖 درس را شروع کو", disabled=not topic):
        with st.spinner("معلم درس را آماده میکند..."):
            text, err = ask_ai(
                [
                    {
                        "role": "user",
                        "text": (
                            f"یک درس کوتاه دربارهٔ «{topic}» بده: ۱) نکتهٔ اصلی "
                            "۲) پنج مثال انگلیسی با ترجمهٔ دری ۳) یک اشتباه رایج "
                            "شاگردان دری‌زبان. تمرین ننویس، چون امتحان جدا است."
                        ),
                    }
                ],
                teacher_prompt(level),
            )
        if text:
            st.session_state.lesson = {"topic": topic, "text": text}
        else:
            st.error(f"درس ساخته نشد: {err}")

    lesson = st.session_state.get("lesson")
    if lesson:
        st.markdown(f"### {lesson['topic']}")
        st.markdown(lesson["text"])
        st.success("درس تمام شد. حالا به تب **📝 امتحان** برو.")

# ------------------------------------------------------------------ exam
with tab_exam:
    st.subheader("امتحان")
    lesson = st.session_state.get("lesson")
    exam = st.session_state.get("exam")

    if not exam:
        default_topic = lesson["topic"] if lesson else TOPICS[0]
        exam_topic = st.text_input("موضوع امتحان", value=default_topic)
        if lesson:
            st.caption("سوال‌ها از درسی که خواندی ساخته میشوند.")
        if st.button("📝 امتحان ۵ سوالی بساز"):
            with st.spinner("معلم سوال‌ها را آماده میکند..."):
                qs, source, err = build_exam(
                    exam_topic, level, lesson["text"] if lesson else ""
                )
            st.session_state.exam = {
                "id": random.randint(1, 10**9),
                "topic": exam_topic,
                "questions": qs,
                "source": source,
                "result": None,
                "review": None,
            }
            if source == "fallback":
                st.session_state.exam_note = (
                    "معلم AI در دسترس نبود، سوال‌های لغت عمومی ساخته شد."
                )
            else:
                st.session_state.exam_note = ""
            st.rerun()

    elif exam["result"] is None:
        if st.session_state.get("exam_note"):
            st.info(st.session_state.exam_note)
        st.caption(f"موضوع: {exam['topic']}")
        with st.form("exam_form"):
            picked = []
            for i, q in enumerate(exam["questions"]):
                st.markdown(
                    f'<div class="card ltr"><b>{i + 1}.</b> {html.escape(q["q"])}</div>',
                    unsafe_allow_html=True,
                )
                picked.append(
                    st.radio(
                        f"سوال {i + 1}",
                        q["options"],
                        index=None,
                        key=f"{exam['id']}_{i}",
                        label_visibility="collapsed",
                    )
                )
            done = st.form_submit_button("✅ پایان امتحان و دیدن نتیجه")
        if done:
            if any(p is None for p in picked):
                st.warning("به همهٔ سوال‌ها جواب بده.")
            else:
                right, wrong = [], []
                for q, p in zip(exam["questions"], picked):
                    item = {
                        "q": q["q"],
                        "yours": p,
                        "correct": q["options"][q["answer"]],
                        "explain": q["explain"],
                    }
                    (right if p == item["correct"] else wrong).append(item)
                conn.execute(
                    "INSERT INTO exam_results (student, topic, score, total) VALUES (?,?,?,?)",
                    (student, exam["topic"], len(right), len(exam["questions"])),
                )
                for w in wrong:
                    conn.execute(
                        "INSERT INTO wrong_answers (student, topic, question, wrong_answer, correct_answer) "
                        "VALUES (?,?,?,?,?)",
                        (student, exam["topic"], w["q"], w["yours"], w["correct"]),
                    )
                conn.commit()
                exam["result"] = {"right": right, "wrong": wrong}
                st.rerun()

    else:
        res = exam["result"]
        total = len(exam["questions"])
        score = len(res["right"])
        pct = score * 100 // total
        st.markdown(f'<p class="score">{score} / {total}</p>', unsafe_allow_html=True)
        st.progress(score / total)
        if pct >= 90:
            st.success(f"{pct}٪ — آفرین! عالی بود 🌟")
        elif pct >= 70:
            st.success(f"{pct}٪ — خیلی خوب!")
        elif pct >= 50:
            st.warning(f"{pct}٪ — قابل قبول، کمی تمرین بیشتر.")
        else:
            st.error(f"{pct}٪ — نگران نباش، درس را دوباره بخوان و امتحان بده.")

        st.markdown(f"#### ✅ جواب‌های درست ({len(res['right'])})")
        if not res["right"]:
            st.write("—")
        for r in res["right"]:
            st.markdown(
                f'<div class="card ok ltr">{html.escape(r["q"])}<br>'
                f"<b>✔ {html.escape(r['correct'])}</b></div>",
                unsafe_allow_html=True,
            )

        st.markdown(f"#### ❌ جواب‌های غلط ({len(res['wrong'])})")
        if not res["wrong"]:
            st.write("هیچ غلطی نداشتی 👏")
        for w in res["wrong"]:
            st.markdown(
                f'<div class="card bad"><div class="ltr">{html.escape(w["q"])}</div>'
                f'جواب تو: <b class="ltr">{html.escape(w["yours"])}</b><br>'
                f'جواب درست: <b class="ltr">{html.escape(w["correct"])}</b><br>'
                f'{html.escape(w["explain"])}</div>',
                unsafe_allow_html=True,
            )

        if res["wrong"]:
            if st.button("👩‍🏫 معلم غلط‌هایم را توضیح بدهد"):
                lines = "\n".join(
                    f"- {w['q']} | جواب من: {w['yours']} | جواب درست: {w['correct']}"
                    for w in res["wrong"]
                )
                with st.spinner("معلم توضیح میدهد..."):
                    text, err = ask_ai(
                        [
                            {
                                "role": "user",
                                "text": "این‌ها اشتباهات من در امتحان بود:\n"
                                + lines
                                + "\nبرای هر کدام کوتاه توضیح بده چرا غلط بود و یک "
                                "مثال جمله بنویس.",
                            }
                        ],
                        teacher_prompt(level),
                    )
                exam["review"] = text or f"خطا: {err}"
                st.rerun()
        if exam.get("review"):
            st.markdown("#### 👩‍🏫 توضیح معلم")
            st.markdown(exam["review"])

        if st.button("🔄 امتحان جدید"):
            del st.session_state["exam"]
            st.rerun()

# ------------------------------------------------------------------ progress
with tab_progress:
    st.subheader("پیشرفت من")
    results = conn.execute(
        "SELECT topic, score, total, created FROM exam_results WHERE student=? ORDER BY id",
        (student,),
    ).fetchall()
    if not results:
        st.info("هنوز امتحانی ندادی.")
    else:
        st.line_chart([r[1] * 100 / r[2] for r in results])
        st.caption("نمرهٔ هر امتحان (٪)")
        st.dataframe(
            [
                {"موضوع": r[0], "نمره": f"{r[1]}/{r[2]}", "زمان": r[3]}
                for r in reversed(results)
            ],
            use_container_width=True,
        )
    st.markdown("#### اشتباهات اخیر")
    wr = conn.execute(
        "SELECT question, wrong_answer, correct_answer FROM wrong_answers "
        "WHERE student=? ORDER BY id DESC LIMIT 15",
        (student,),
    ).fetchall()
    if not wr:
        st.write("—")
    else:
        st.dataframe(
            [{"سوال": a, "جواب تو": b, "جواب درست": c} for a, b, c in wr],
            use_container_width=True,
        )

# ------------------------------------------------------------------ chat
with tab_chat:
    st.subheader("از معلم بپرس")
    if "chat" not in st.session_state:
        st.session_state.chat = []
    for m in st.session_state.chat:
        with st.chat_message("user" if m["role"] == "user" else "assistant"):
            st.markdown(m["text"])
    msg = st.chat_input("سوالت را بنویس یا یک جملهٔ انگلیسی بفرست تا تصحیح کنم...")
    if msg:
        st.session_state.chat.append({"role": "user", "text": msg})
        with st.spinner("..."):
            text, err = ask_ai(
                st.session_state.chat,
                teacher_prompt(level)
                + " اگر جملهٔ انگلیسی نوشت، تصحیحش کو و دلیل غلط‌ها را بگو.",
            )
        st.session_state.chat.append({"role": "model", "text": text or f"خطا: {err}"})
        st.rerun()
