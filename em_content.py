"""EnglishMate content loader: vocabulary packs and grammar lessons.

Vocabulary lives in data/vocab/*.json (any number of files).
Grammar lives in data/grammar.json.
"""
import json
from pathlib import Path

import streamlit as st

BASE = Path(__file__).resolve().parent / "data"
LEVELS = {
    "beginner": "مبتدی",
    "intermediate": "متوسط",
    "advanced": "پیشرفته",
}
POS_FA = {
    "noun": "اسم", "verb": "فعل", "adjective": "صفت", "adverb": "قید",
    "interjection": "صوت", "phrasal verb": "فعل دوکلمه‌ای",
    "expression": "عبارت",
}
KEYS = ("w", "pos", "fa", "def", "ex", "exfa", "topic")


@st.cache_data
def load_vocab():
    """Returns (words, errors). Bad files are skipped and reported."""
    words, errors, seen = [], [], set()
    for path in sorted((BASE / "vocab").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            level = data["level"]
            if level not in LEVELS:
                raise ValueError(f"unknown level {level}")
            for w in data["words"]:
                if any(k not in w for k in KEYS):
                    raise ValueError(f"missing field in {w.get('w')}")
                wid = f"{level}:{w['w'].lower()}"
                if wid in seen:
                    continue
                seen.add(wid)
                item = dict(w)
                item["level"] = level
                item["id"] = wid
                words.append(item)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    return words, errors


@st.cache_data
def load_grammar():
    try:
        path = BASE / "grammar.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["lessons"], []
    except Exception as exc:
        return [], [f"grammar.json: {exc}"]


def words_for(level):
    return [w for w in load_vocab()[0] if w["level"] == level]


def topics_for(level):
    return sorted({w["topic"] for w in words_for(level)})


def word_by_id(wid):
    for w in load_vocab()[0]:
        if w["id"] == wid:
            return w
    return None
