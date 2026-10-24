"""EnglishMate AI helpers (Gemini). Optional: needs GEMINI_API_KEY."""
import os
import re
import time

import requests
import streamlit as st

MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{}:generateContent"
)


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
    """Returns (text, error). Retries busy models, then the next model."""
    key = get_secret("GEMINI_API_KEY")
    if not key:
        return None, "NO_KEY"
    models = []
    custom = get_secret("GEMINI_MODEL")
    if custom:
        models.append(custom)
    models += [m for m in MODELS if m not in models]
    body = {
        "system_instruction": {"parts": [{"text": system_text}]},
        "contents": [
            {"role": m["role"], "parts": [{"text": m["text"]}]}
            for m in history
        ],
    }
    last_err = "unknown error"
    for model in models:
        for _attempt in range(2):
            try:
                r = requests.post(
                    API_URL.format(model),
                    headers={"x-goog-api-key": key},
                    json=body, timeout=60,
                )
                data = r.json()
            except Exception as e:
                last_err = f"connection: {e}"
                time.sleep(1)
                continue
            if "candidates" in data:
                try:
                    cand = data["candidates"][0]
                    return cand["content"]["parts"][0]["text"], None
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
    busy = ("demand", "overload", "unavailable", "quota")
    if any(w in low for w in busy):
        return "مدل AI در این لحظه شلوغ است. چند دقیقه بعد دوباره امتحان کو."
    return f"خطا از سرویس AI: {err}"


def teacher_prompt(level_fa):
    return (
        "You are a kind, patient English teacher for Afghan students "
        f"who speak Dari. Student level: {level_fa}. "
        "Explain in simple English AND in simple Dari. "
        "Keep answers short and well organised for a phone screen. "
        "Use Markdown."
    )


def split_practice(text):
    parts = re.split(r"-{3}\s*ANSWERS\s*-{3}", text, maxsplit=1, flags=re.I)
    questions = parts[0].strip()
    answers = parts[1].strip() if len(parts) > 1 else ""
    return questions, answers
