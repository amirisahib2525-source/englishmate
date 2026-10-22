import html
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
