"""Vocabulary page: daily lessons, flashcards, review and search."""
import streamlit as st

from em_content import LEVELS, POS_FA, topics_for, word_by_id, words_for
from em_db import (
    current_level, current_student, set_word_status, word_status_map,
)
from em_style import card, esc, speak_button

BATCH = 10
STATUS_ICON = {"learned": "✅", "difficult": "⭐"}


# ------------------------------------------------------------- cards logic
def start_cards(student, level, kind):
    status = word_status_map(student)
    words = words_for(level)
    if kind == "new":
        ids = [w["id"] for w in words if status.get(w["id"]) != "learned"]
        ids = ids[:BATCH]
        label = "درس امروز"
    elif kind == "difficult":
        ids = [w["id"] for w in words if status.get(w["id"]) == "difficult"]
        label = "مرور لغات دشوار"
    else:
        ids = [w["id"] for w in words if status.get(w["id"]) == "learned"]
        label = "مرور لغات یاد گرفته"
    st.session_state.cards = {
        "ids": ids, "pos": 0, "show": False, "label": label, "kind": kind,
        "student": student, "level": level, "learned": 0, "difficult": 0,
    }


def start_cards_cb(kind):
    start_cards(current_student(), current_level(), kind)


def cards_toggle():
    c = st.session_state.get("cards")
    if c and c["pos"] < len(c["ids"]):
        c["show"] = not c["show"]


def cards_prev():
    c = st.session_state.get("cards")
    if c and c["pos"] > 0:
        c["pos"] -= 1
        c["show"] = False


def cards_next():
    c = st.session_state.get("cards")
    if c and c["pos"] < len(c["ids"]):
        c["pos"] += 1
        c["show"] = False


def cards_mark(status):
    c = st.session_state.get("cards")
    if not c or c["pos"] >= len(c["ids"]):
        return
    set_word_status(c["student"], c["ids"][c["pos"]], status)
    c[status] += 1
    c["pos"] += 1
    c["show"] = False


def cards_close():
    st.session_state.pop("cards", None)


# ------------------------------------------------------------- cards UI
def word_card(w, show_meaning, status=None):
    icon = STATUS_ICON.get(status, "")
    head = (f'<div class="word ltr">{esc(w["w"])} {icon} '
            f'<span class="badge">{esc(POS_FA.get(w["pos"], w["pos"]))}</span>'
            f'<span class="badge">{esc(w["topic"])}</span></div>')
    body = ""
    if show_meaning:
        body += (f'<div class="mean">{esc(w["fa"])}</div>'
                 f'<div class="ex ltr">{esc(w["def"])}</div>')
    body += f'<div class="ex ltr">“{esc(w["ex"])}”</div>'
    if show_meaning:
        body += f'<div class="ex">{esc(w["exfa"])}</div>'
    card(head + body)


def cards_view(c):
    total = len(c["ids"])
    st.subheader(c["label"])
    if total == 0:
        st.info("لغتی برای نمایش نیست.")
        st.button("بستن", on_click=cards_close, key="cards_close0")
        return
    if c["pos"] >= total:
        st.success(f"تمام شد! یاد گرفتم: {c['learned']} • "
                   f"دشوار: {c['difficult']}")
        if c["kind"] == "new":
            st.button(f"▶ {BATCH} لغت دیگر", on_click=start_cards_cb,
                      args=("new",), key="cards_more")
        st.button("بستن", on_click=cards_close, key="cards_close1")
        return
    w = word_by_id(c["ids"][c["pos"]])
    status = word_status_map(c["student"]).get(w["id"])
    st.progress(c["pos"] / total)
    st.caption(f"لغت {c['pos'] + 1} از {total}")
    word_card(w, c["show"], status)
    speak_button(w["w"])
    pos = c["pos"]
    label = "🙈 پنهان کردن معنی" if c["show"] else "👀 نمایش معنی"
    st.button(label, on_click=cards_toggle, key=f"ct_{pos}")
    a, b = st.columns(2)
    a.button("✅ یاد گرفتم", on_click=cards_mark, args=("learned",),
             key=f"cl_{pos}")
    b.button("⭐ دشوار است", on_click=cards_mark, args=("difficult",),
             key=f"cd_{pos}")
    p, n = st.columns(2)
    p.button("➡️ قبلی", on_click=cards_prev, key=f"cp_{pos}",
             disabled=pos == 0)
    n.button("⬅️ بعدی", on_click=cards_next, key=f"cn_{pos}")
    st.button("خروج", on_click=cards_close, key=f"cx_{pos}")


# ------------------------------------------------------------- tabs
def tab_daily(student, level):
    words = words_for(level)
    status = word_status_map(student)
    learned = sum(1 for w in words if status.get(w["id"]) == "learned")
    st.markdown(f"##### سطح {LEVELS[level]}")
    if words:
        st.progress(learned / len(words))
        st.caption(f"{learned} از {len(words)} لغت یاد گرفته شده")
    left = len(words) - learned
    if left > 0:
        st.button(f"▶ شروع درس امروز ({min(BATCH, left)} لغت)",
                  on_click=start_cards_cb, args=("new",), key="start_new")
    elif words:
        st.success("همهٔ لغات این سطح را یاد گرفتی! 🎉")


def tab_review(student, level):
    status = word_status_map(student)
    words = words_for(level)
    hard = [w for w in words if status.get(w["id"]) == "difficult"]
    done = [w for w in words if status.get(w["id"]) == "learned"]
    st.write(f"⭐ لغات دشوار: {len(hard)} • ✅ لغات یاد گرفته: {len(done)}")
    if hard:
        st.button("⭐ مرور لغات دشوار", on_click=start_cards_cb,
                  args=("difficult",), key="start_hard")
    else:
        st.info("هنوز لغت دشواری ذخیره نکرده‌ای.")
    if done:
        st.button("✅ مرور لغات یاد گرفته", on_click=start_cards_cb,
                  args=("learned",), key="start_done")


def tab_list(student, level):
    words = words_for(level)
    status = word_status_map(student)
    c1, c2 = st.columns(2)
    search = c1.text_input("🔎 جستجو", key="vocab_search",
                           placeholder="English یا دری").strip().lower()
    topic = c2.selectbox("📂 دسته", ["همه"] + topics_for(level),
                         key="vocab_topic")
    show = st.checkbox("نمایش معنی‌ها", value=True, key="vocab_show")
    shown = [
        w for w in words
        if (topic == "همه" or w["topic"] == topic)
        and (not search or search in w["w"].lower() or search in w["fa"])
    ]
    limit = st.session_state.get("vocab_limit", 20)
    st.caption(f"{len(shown)} لغت")
    for w in shown[:limit]:
        word_card(w, show, status.get(w["id"]))
    if len(shown) > limit:
        st.button("نمایش بیشتر", key="vocab_more",
                  on_click=lambda: st.session_state.update(
                      vocab_limit=limit + 20))
    if not shown:
        st.info("لغتی پیدا نشد.")


def page_vocab(student, level):
    st.subheader("📚 لغات")
    cards = st.session_state.get("cards")
    if cards:
        cards_view(cards)
        return
    if not words_for(level):
        st.info("برای این سطح هنوز لغتی اضافه نشده است.")
        return
    t1, t2, t3 = st.tabs(["📅 درس امروز", "⭐ مرور", "🔎 فهرست"])
    with t1:
        tab_daily(student, level)
    with t2:
        tab_review(student, level)
    with t3:
        tab_list(student, level)
