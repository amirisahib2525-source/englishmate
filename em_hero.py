"""Home banner. Uses assets/banner.png (or .jpg/.jpeg) if you upload one."""
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent / "assets"
NAMES = ("banner.png", "banner.jpg", "banner.jpeg")

IMG_CSS = """
<style>
[data-testid="stImage"] img {width:100%; border-radius:18px;
  border:1px solid #27479a;}
</style>
"""

TEXT_HERO = (
    '<div class="hero"><h1>📘 EnglishMate AI</h1>'
    "<p>یادگیری انگلیسی، آسان‌تر از همیشه</p></div>"
)


def banner_path():
    for name in NAMES:
        path = ASSETS / name
        if path.exists():
            return path
    return None


def show_hero():
    path = banner_path()
    if path:
        try:
            st.markdown(IMG_CSS, unsafe_allow_html=True)
            st.image(str(path))
            return
        except Exception:
            pass
    st.markdown(TEXT_HERO, unsafe_allow_html=True)
