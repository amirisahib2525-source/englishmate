import sqlite3
import random
import streamlit as st

st.set_page_config(page_title="EnglishMate", page_icon="📘")

conn = sqlite3.connect("englishmate.db", check_same_thread=False)
conn.execute(
    """CREATE TABLE IF NOT EXISTS mistakes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student TEXT,
        word TEXT,
        wrong_answer TEXT,
        correct_answer TEXT,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
)
conn.commit()

WORDS = [
    ("apple", "سیب"), ("book", "کتاب"), ("water", "آب"),
    ("house", "خانه"), ("friend", "دوست"), ("school", "مکتب"),
    ("teacher", "معلم"), ("student", "شاگرد"), ("city", "شهر"),
    ("food", "غذا"), ("family", "فامیل"), ("work", "کار"),
    ("morning", "صبح"), ("night", "شب"), ("big", "بزرگ"),
    ("small", "کوچک"), ("good", "خوب"), ("bad", "بد"),
    ("learn", "یاد گرفتن"), ("write", "نوشتن"),
]

st.sidebar.title("📘 EnglishMate")
student = st.sidebar.text_input("نام شاگرد", value="مهمان")
page = st.sidebar.radio("صفحه", ["لغات", "کویز", "اشتباهات من"])

if page == "لغات":
    st.title("لغات امروز")
    seed = st.session_state.setdefault("seed", 0)
    rnd = random.Random(seed)
    today = rnd.sample(WORDS, 5)
    for en, fa in today:
        st.markdown(f"**{en}**  →  {fa}")
    if st.button("لغات جدید"):
        st.session_state.seed += 1
        st.rerun()

elif page == "کویز":
    st.title("کویز")

    if "q" not in st.session_state:
        st.session_state.q = random.choice(WORDS)
        st.session_state.score = 0
        st.session_state.total = 0
        st.session_state.feedback = ""

    en, fa = st.session_state.q
    st.subheader(f"معنی «{en}» چیست؟")

    wrong = [w[1] for w in WORDS if w[1] != fa]
    key = f"opts_{en}"
    if key not in st.session_state:
        opts = random.sample(wrong, 3) + [fa]
        random.shuffle(opts)
        st.session_state[key] = opts
    options = st.session_state[key]

    choice = st.radio("جواب", options, key=f"radio_{en}")

    if st.button("ثبت جواب"):
        st.session_state.total += 1
        if choice == fa:
            st.session_state.score += 1
            st.session_state.feedback = "✅ درست!"
        else:
            st.session_state.feedback = f"❌ غلط. جواب درست: {fa}"
            conn.execute(
                "INSERT INTO mistakes (student, word, wrong_answer, correct_answer) VALUES (?,?,?,?)",
                (student, en, choice, fa),
            )
            conn.commit()
        st.session_state.q = random.choice(WORDS)

    if st.session_state.feedback:
        st.info(st.session_state.feedback)
    st.write(f"نمره: {st.session_state.score} / {st.session_state.total}")

else:
    st.title("اشتباهات من")
    rows = conn.execute(
        "SELECT word, wrong_answer, correct_answer, created FROM mistakes WHERE student=? ORDER BY id DESC",
        (student,),
    ).fetchall()
    if not rows:
        st.success("هنوز اشتباهی نداری 👏")
    else:
        st.write(f"مجموع اشتباهات: {len(rows)}")
        st.dataframe(
            [
                {"لغت": r[0], "جواب تو": r[1], "جواب درست": r[2], "زمان": r[3]}
                for r in rows
            ],
            use_container_width=True,
        )
