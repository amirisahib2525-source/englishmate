"""EnglishMate main screen: profile, navigation, home, AI teacher, progress."""
import streamlit as st

from em_ai import (
    ai_available, ask_ai, friendly_error, split_practice, teacher_prompt,
)
from em_content import LEVELS, load_grammar, load_vocab, words_for
from em_db import current_level, current_student, get_stats, q_all, word_status_map
from em_grammar_page import page_grammar
from em_quiz_page import page_quiz
from em_style import card, esc, inject_css
from em_vocab_page import page_vocab

NAV = {
    "home": "🏠 خانه", "vocab": "📚 لغات", "grammar": "📘 گرامر",
    "quiz": "📝 کویز", "ai": "🤖 معلم AI", "progress": "📊 پیشرفت",
}
PAGES = list(NAV.values())


def pct_text(value):
    return "—" if value is None else f"{value:.0f}٪"


def goto(page):
    st.session_state["nav"] = page


# ------------------------------------------------------------- profile
def init_profile():
    ss = st.session_state
    if ss.get("profile_ready"):
        return
    ss["profile_ready"] = True
    try:
        name = st.query_params.get("name", "")
        level = st.query_params.get("level", "beginner")
    except Exception:
        name, level = "", "beginner"
    ss.setdefault("student_input", name)
    ss.setdefault("level", level if level in LEVELS else "beginner")
    ss.setdefault("nav", PAGES[0])


def save_profile():
    """Keep name and level in the page address so a refresh keeps them."""
    try:
        name = (st.session_state.get("student_input") or "").strip()
        if name:
            st.query_params["name"] = name
        elif "name" in st.query_params:
            del st.query_params["name"]
        st.query_params["level"] = current_level()
    except Exception:
        pass


def profile_row():
    c1, c2 = st.columns(2)
    c1.text_input("👤 نام شاگرد", key="student_input",
                  placeholder="نام خود را بنویس", max_chars=40,
                  on_change=save_profile)
    c2.selectbox("📶 سطح", list(LEVELS), format_func=LEVELS.get,
                 key="level", on_change=save_profile)
    if not (st.session_state.get("student_input") or "").strip():
        st.caption("نام را بنویس تا نتیجه‌ها به نام تو ذخیره شود.")


def navigation():
    try:
        box = st.container(key="navbox")
    except TypeError:
        box = st.container()
    with box:
        st.radio("بخش", PAGES, horizontal=True, key="nav",
                 label_visibility="collapsed")


# ------------------------------------------------------------- home
def level_progress(student, level):
    words = words_for(level)
    status = word_status_map(student)
    learned = sum(1 for w in words if status.get(w["id"]) == "learned")
    return learned, len(words)


def recommendation(stats, learned, total, level):
    lvl = LEVELS[level]
    if stats["difficult"] > 0:
        return f"{stats['difficult']} لغت دشوار داری. امروز آن‌ها را مرور کو."
    if total and learned < total:
        return f"امروز ۱۰ لغت جدید از سطح {lvl} یاد بگیر."
    if stats["quizzes"] == 0:
        return "یک کویز کوتاه بده تا سطحت را بسنجی."
    return "آفرین! یک درس گرامر بخوان یا به سطح بعدی برو."


def page_home(student, level):
    stats = get_stats(student)
    learned, total = level_progress(student, level)
    st.markdown(f"### سلام {esc(student)} 👋")
    st.write(f"سطح فعلی تو: **{LEVELS[level]}**")
    c1, c2, c3 = st.columns(3)
    c1.metric("لغات یاد گرفته", stats["learned"])
    c2.metric("اوسط نمرهٔ کویز", pct_text(stats["avg"]))
    c3.metric("کویزها", stats["quizzes"])
    if total:
        st.progress(learned / total)
        st.caption(f"پیشرفت سطح {LEVELS[level]}: {learned} از {total} لغت")
    card("💡 <b>پیشنهاد امروز</b><br>"
         + esc(recommendation(stats, learned, total, level)), "tip")
    a, b, c = st.columns(3)
    a.button("📚 لغات", on_click=goto, args=(NAV["vocab"],), key="h_vocab")
    b.button("📘 گرامر", on_click=goto, args=(NAV["grammar"],), key="h_gram")
    c.button("📝 کویز", on_click=goto, args=(NAV["quiz"],), key="h_quiz")
    if not ai_available():
        st.caption("معلم AI نیاز به تنظیم کلید دارد؛ بقیهٔ بخش‌ها بدون AI "
                   "کار میکنند.")


# ------------------------------------------------------------- AI teacher
def ai_setup_help():
    st.info(
        "معلم AI برای کار کردن به کلید Gemini نیاز دارد. بدون آن، لغات، "
        "گرامر، کویز و پیشرفت کار میکنند.\n\n"
        "۱) از aistudio.google.com/apikey کلید رایگان بگیر.\n\n"
        "۲) در Streamlit: Manage app ← Settings ← Secrets و بنویس: "
        "`GEMINI_API_KEY = \"کلید-تو\"`"
    )


def ai_run(prompt, system, out_key):
    with st.spinner("معلم فکر میکند..."):
        text, err = ask_ai([{"role": "user", "text": prompt}], system)
    st.session_state[out_key] = text or "ERR:" + friendly_error(err)


def ai_show(out_key):
    out = st.session_state.get(out_key)
    if not out:
        return
    if out.startswith("ERR:"):
        st.error(out[4:])
    else:
        st.markdown(out)


def ai_fix(system):
    sentence = st.text_area("جملهٔ انگلیسی‌ات را بنویس", key="ai_sentence")
    if st.button("✍️ تصحیح کو", disabled=not sentence.strip(), key="ai_fix"):
        ai_run(
            f"Student sentence: {sentence}\nReply in Markdown with: "
            "1) **Corrected sentence** 2) **Why (simple English)** "
            "3) **چرا (دری ساده)** 4) two new example sentences with Dari "
            "translation. If the sentence is already correct, say so.",
            system, "ai_fix_out")
    ai_show("ai_fix_out")


def ai_lesson(system):
    topic = st.text_input("موضوع درس", value="Present simple",
                          key="ai_topic")
    if st.button("📖 درس بده", disabled=not topic.strip(), key="ai_lesson"):
        ai_run(
            f"Give a short lesson about: {topic}. Include the key rule, "
            "five examples with Dari translation, and one common mistake of "
            "Dari speakers. No exercises.", system, "ai_lesson_out")
    ai_show("ai_lesson_out")


def ai_practice(student, system):
    rows = q_all(
        "SELECT question, wrong_answer, correct_answer FROM wrong_answers "
        "WHERE student=? ORDER BY id DESC LIMIT 10", (student,))
    if not rows:
        st.info("هنوز اشتباهی ذخیره نشده. اول یک کویز بده.")
        return
    if st.button("🎯 تمرین بساز", key="ai_practice"):
        lines = "\n".join(
            f"- {a} | my answer: {b} | correct: {c}" for a, b, c in rows)
        ai_run(
            "These are my recent mistakes:\n" + lines +
            "\nWrite 5 NEW multiple-choice practice questions (options A-D) "
            "that target the same weaknesses. Write the questions first. "
            "Then write a line containing exactly ---ANSWERS--- and after it "
            "the answers with a short Dari explanation.",
            system, "ai_practice_out")
    out = st.session_state.get("ai_practice_out")
    if not out:
        return
    if out.startswith("ERR:"):
        st.error(out[4:])
        return
    questions, answers = split_practice(out)
    st.markdown(questions)
    if answers:
        with st.expander("✅ جواب‌ها و توضیح"):
            st.markdown(answers)


def ai_chat(system):
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


def page_ai(student, level):
    st.subheader("🤖 معلم هوش مصنوعی")
    if not ai_available():
        ai_setup_help()
        return
    tools = ["✍️ تصحیح جمله", "📖 درس کوتاه", "🎯 تمرین از اشتباهاتم",
             "💬 پرسش آزاد"]
    tool = st.selectbox("ابزار", tools, key="ai_tool")
    system = teacher_prompt(LEVELS[level])
    if tool == tools[0]:
        ai_fix(system)
    elif tool == tools[1]:
        ai_lesson(system)
    elif tool == tools[2]:
        ai_practice(student, system)
    else:
        ai_chat(system)


# ------------------------------------------------------------- progress
def page_progress(student):
    st.subheader("📊 پیشرفت من")
    stats = get_stats(student)
    c1, c2 = st.columns(2)
    c1.metric("لغات یاد گرفته", stats["learned"])
    c2.metric("لغات دشوار", stats["difficult"])
    c3, c4 = st.columns(2)
    c3.metric("اوسط نمره", pct_text(stats["avg"]))
    c4.metric("بهترین نمره", pct_text(stats["best"]))
    st.markdown("##### پیشرفت لغات در هر سطح")
    for code, name in LEVELS.items():
        learned, total = level_progress(student, code)
        if total:
            st.progress(learned / total)
            st.caption(f"{name}: {learned} از {total}")
    t_scores, t_mistakes = st.tabs(["📈 نمره‌ها", "❌ اشتباهات من"])
    with t_scores:
        rows = q_all(
            "SELECT topic, score, total, created FROM exam_results "
            "WHERE student=? ORDER BY id", (student,))
        if not rows:
            st.info("هنوز کویز یا تمرینی ندادی.")
        else:
            if len(rows) >= 2:
                st.line_chart([r[1] * 100 / r[2] for r in rows])
            st.dataframe([
                {"نوع": r[0], "نمره": f"{r[1]}/{r[2]}",
                 "درصد": f"{r[1] * 100 // r[2]}٪", "زمان (UTC)": r[3]}
                for r in reversed(rows[-20:])])
    with t_mistakes:
        rows = q_all(
            "SELECT question, wrong_answer, correct_answer, created "
            "FROM wrong_answers WHERE student=? ORDER BY id DESC LIMIT 50",
            (student,))
        if not rows:
            st.success("اشتباهی ذخیره نشده 👏")
        else:
            st.dataframe([
                {"سوال": a, "جواب تو": b, "جواب درست": c, "زمان (UTC)": d}
                for a, b, c, d in rows])
    st.caption("توجه: روی Streamlit Community Cloud فایل دیتابیس "
               "ممکن است بعد از ری‌استارت پاک شود.")


# ------------------------------------------------------------- main
def data_warnings():
    errors = load_vocab()[1] + load_grammar()[1]
    if errors:
        st.warning("بعضی فایل‌های داده خوانده نشدند: " + " | ".join(errors))


def main():
    inject_css()
    init_profile()
    st.markdown(
        '<div class="hero"><h1>📘 EnglishMate AI</h1>'
        "<p>یادگیری انگلیسی، آسان‌تر از همیشه</p></div>",
        unsafe_allow_html=True,
    )
    profile_row()
    navigation()
    data_warnings()
    student, level = current_student(), current_level()
    page = st.session_state["nav"]
    if page == NAV["home"]:
        page_home(student, level)
    elif page == NAV["vocab"]:
        page_vocab(student, level)
    elif page == NAV["grammar"]:
        page_grammar()
    elif page == NAV["quiz"]:
        page_quiz()
    elif page == NAV["ai"]:
        page_ai(student, level)
    else:
        page_progress(student)
