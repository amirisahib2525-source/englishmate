"""Quiz page: setup, question with instant feedback, final result."""
import streamlit as st

from em_content import LEVELS, load_grammar
from em_db import current_level
from em_quiz import (
    MODE_LABELS, answer_quiz, next_quiz, reset_quiz, start_quiz_cb,
)
from em_style import card, esc


def quiz_setup(level):
    st.markdown(f"سطح انتخاب‌شده: **{LEVELS[level]}**")
    st.radio("نوع کویز", list(MODE_LABELS), format_func=MODE_LABELS.get,
             key="quiz_mode", horizontal=True, index=2)
    st.radio("تعداد سوال", [5, 10], key="quiz_n", horizontal=True, index=0)
    if st.session_state.get("quiz_mode") in ("grammar", "mixed"):
        lessons = load_grammar()[0]
        names = {"all": "همهٔ زمان‌ها"}
        names.update({l["id"]: l["en"] for l in lessons})
        st.selectbox("زمان گرامر", list(names), format_func=names.get,
                     key="quiz_tense")
    if st.session_state.get("quiz_error"):
        st.warning(st.session_state["quiz_error"])
    st.button("🚀 شروع کویز", on_click=start_quiz_cb, key="quiz_start")


def quiz_question(qz):
    total, pos = len(qz["questions"]), qz["pos"]
    q = qz["questions"][pos]
    st.progress((pos + (1 if qz["answered"] else 0)) / total)
    st.caption(f"{qz['label']} • سوال {pos + 1} از {total} • "
               f"نمره تا حالا: {qz['score']}")
    card(esc(q["q"]), "q " + q["qdir"])
    qid = qz["id"]
    if not qz["answered"]:
        for i, opt in enumerate(q["options"]):
            st.button(opt, on_click=answer_quiz, args=(i,),
                      key=f"o_{qid}_{pos}_{i}")
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
            st.markdown(f'<div class="{cls}">{mark}{esc(opt)}</div>',
                        unsafe_allow_html=True)
        if qz["picked"] == q["answer"]:
            st.success("✅ درست!")
        else:
            st.error("❌ غلط. جواب درست با رنگ سبز نشان داده شد.")
        st.info(q["explain"])
        label = "🏁 دیدن نتیجه" if pos + 1 >= total else "➡️ سوال بعدی"
        st.button(label, on_click=next_quiz, key=f"n_{qid}_{pos}")
    st.button("خروج از کویز", on_click=reset_quiz, key=f"x_{qid}_{pos}")


def quiz_result(qz):
    total, score = len(qz["questions"]), qz["score"]
    pct = score * 100 // total
    st.markdown(f'<p class="score">{score} / {total}</p>',
                unsafe_allow_html=True)
    st.progress(score / total)
    if pct >= 90:
        st.success(f"{pct}٪ — آفرین! عالی بود 🌟")
    elif pct >= 70:
        st.success(f"{pct}٪ — خیلی خوب!")
    elif pct >= 50:
        st.warning(f"{pct}٪ — قابل قبول، کمی تمرین بیشتر.")
    else:
        st.error(f"{pct}٪ — نگران نباش، درس را مرور کو و دوباره امتحان بده.")
    right = [x for x in qz["log"] if x["ok"]]
    wrong = [x for x in qz["log"] if not x["ok"]]
    st.markdown(f"#### ✅ جواب‌های درست ({len(right)})")
    if not right:
        st.write("—")
    for x in right:
        card(f'<div class="{x["qdir"]}">{esc(x["q"])}</div>'
             f'<b>✔ {esc(x["correct"])}</b>', "ok")
    st.markdown(f"#### ❌ جواب‌های غلط ({len(wrong)})")
    if not wrong:
        st.write("هیچ غلطی نداشتی 👏")
    for x in wrong:
        card(f'<div class="{x["qdir"]}">{esc(x["q"])}</div>'
             f'جواب تو: <b>{esc(x["picked"])}</b><br>'
             f'جواب درست: <b>{esc(x["correct"])}</b><br>'
             f'{esc(x["explain"])}', "bad")
    st.button("🔄 کویز جدید", on_click=reset_quiz, key="quiz_again")
    st.caption("نتیجه و اشتباهات در بخش 📊 پیشرفت من ذخیره شد.")


def page_quiz():
    st.subheader("📝 کویز")
    qz = st.session_state.get("quiz")
    if not qz:
        quiz_setup(current_level())
    elif qz["finished"]:
        quiz_result(qz)
    else:
        quiz_question(qz)
