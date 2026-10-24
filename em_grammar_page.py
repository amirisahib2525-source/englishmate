"""English Grammar page: eight tense lessons with practice and quiz."""
import re

import streamlit as st

from em_content import load_grammar
from em_db import current_student, q_run
from em_style import card, chips, esc


def norm(text):
    text = str(text).lower().replace("’", "'").strip()
    text = re.sub(r"[.!?]+$", "", text)
    return re.sub(r"\s+", " ", text)


def is_correct(user, answer):
    return norm(user) in [norm(a) for a in answer.split("|")]


def save_attempt(lesson, kind, score, total):
    q_run(
        "INSERT INTO exam_results (student, topic, score, total) "
        "VALUES (?,?,?,?)",
        (current_student(), f"گرامر: {lesson['en']} ({kind})", score, total),
    )


def example_block(title, pairs):
    rows = "".join(
        f'<div class="ltr"><b>{esc(en)}</b></div><div class="ex">{esc(fa)}</div>'
        for en, fa in pairs
    )
    card(f"<b>{title}</b>{rows}")


def tab_lesson(lesson):
    card(esc(lesson["explain"]), "tip")
    f = lesson["formula"]
    st.markdown("##### 🧩 فرمول جمله")
    st.markdown(
        f'<div class="formula">✔ {esc(f["affirmative"])}</div>'
        f'<div class="formula">✘ {esc(f["negative"])}</div>'
        f'<div class="formula">? {esc(f["question"])}</div>',
        unsafe_allow_html=True,
    )
    ex = lesson["examples"]
    example_block("✔ جملهٔ مثبت", ex["affirmative"])
    example_block("✘ جملهٔ منفی", ex["negative"])
    example_block("? سوالی", ex["question"])
    card("<b>⏰ کلمه‌های زمانی</b><br>" + chips(lesson["time"]))
    items = "".join(f"<li>{esc(x)}</li>" for x in lesson["when"])
    card(f"<b>📌 چه وقت استفاده میشود؟</b><ul>{items}</ul>")
    st.markdown("##### ⚠️ اشتباهات رایج")
    for wrong, right, note in lesson["mistakes"]:
        card(f'<div class="ltr">❌ {esc(wrong)}</div>'
             f'<div class="ltr">✅ <b>{esc(right)}</b></div>'
             f'<div class="ex">{esc(note)}</div>', "bad")


def tab_practice(lesson):
    st.write("جاهای خالی را پر کو، بعد دکمهٔ بررسی را بزن.")
    exs = lesson["exercises"]
    lid = lesson["id"]
    with st.form(f"form_ex_{lid}"):
        answers = [
            st.text_input(f"{i + 1}. {e['q']}", key=f"ex_{lid}_{i}")
            for i, e in enumerate(exs)
        ]
        done = st.form_submit_button("✅ بررسی جواب‌ها")
    if not done:
        return
    score = 0
    for e, user in zip(exs, answers):
        ok = is_correct(user, e["a"])
        score += ok
        correct = e["a"].split("|")[0]
        if ok:
            st.success(f"✅ {e['q']} → {correct}")
        else:
            st.error(f"❌ {e['q']} → جواب درست: {correct}\n\n💡 {e['hint']}")
    st.info(f"نمره: {score} / {len(exs)}")
    save_attempt(lesson, "تمرین", score, len(exs))


def tab_mcq(lesson):
    lid = lesson["id"]
    mcq = lesson["mcq"]
    with st.form(f"form_mcq_{lid}"):
        picks = []
        for i, m in enumerate(mcq):
            st.markdown(f'<div class="card q ltr">{i + 1}. {esc(m["q"])}</div>',
                        unsafe_allow_html=True)
            picks.append(st.radio(f"سوال {i + 1}", m["options"], index=None,
                                  key=f"mcq_{lid}_{i}",
                                  label_visibility="collapsed"))
        done = st.form_submit_button("✅ بررسی جواب‌ها")
    if not done:
        return
    if any(p is None for p in picks):
        st.warning("به همهٔ سوال‌ها جواب بده.")
        return
    score = 0
    for m, p in zip(mcq, picks):
        ok = p == m["answer"]
        score += ok
        if ok:
            st.success(f"✅ {m['q']} → {m['answer']}\n\n{m['explain']}")
        else:
            st.error(f"❌ {m['q']}\n\nجواب تو: {p} | جواب درست: "
                     f"{m['answer']}\n\n💡 {m['explain']}")
    st.info(f"نمره: {score} / {len(mcq)}")
    save_attempt(lesson, "سوال‌ها", score, len(mcq))


def page_grammar():
    st.subheader("📘 گرامر انگلیسی")
    lessons, errors = load_grammar()
    if errors or not lessons:
        st.error("فایل data/grammar.json پیدا نشد یا خراب است.")
        return
    names = {l["id"]: f"{i + 1}. {l['en']} — {l['fa']}"
             for i, l in enumerate(lessons)}
    lid = st.selectbox("درس را انتخاب کو", list(names),
                       format_func=names.get, key="grammar_lesson")
    lesson = next(l for l in lessons if l["id"] == lid)
    st.markdown(f"### {esc(lesson['en'])}")
    st.caption(lesson["fa"])
    t1, t2, t3 = st.tabs(["📖 درس", "✍️ تمرین", "🎯 سوال‌ها"])
    with t1:
        tab_lesson(lesson)
    with t2:
        tab_practice(lesson)
    with t3:
        tab_mcq(lesson)
