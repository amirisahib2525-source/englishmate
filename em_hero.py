"""Home header and page background.

If you upload an image (png / jpg / jpeg / webp) to the repository, in the
assets/ folder or the main folder, it becomes the page background.
Any file name works.
"""
import base64
import io
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
EXTS = {".png", ".jpg", ".jpeg", ".webp"}

TEXT_HERO = (
    '<div class="hero"><h1>📘 EnglishMate AI</h1>'
    "<p>یادگیری انگلیسی، آسان‌تر از همیشه</p></div>"
)

BG_CSS = (
    "<style>"
    '[data-testid="stHeader"] {background:transparent;}'
    ".stApp {background:linear-gradient(rgba(10,26,63,.80),"
    "rgba(10,26,63,.90)),url(data:image/jpeg;base64,%s) "
    "center / cover no-repeat fixed !important;}"
    "</style>"
)


def find_banner():
    for folder in (ROOT / "assets", ROOT):
        if not folder.is_dir():
            continue
        files = sorted(
            p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in EXTS
        )
        files.sort(key=lambda p: "banner" not in p.name.lower())
        if files:
            return files[0]
    return None


@st.cache_data
def encode_background(path_str, mtime):
    """Shrinks the image so the page stays fast on a phone."""
    try:
        from PIL import Image
        img = Image.open(path_str).convert("RGB")
        img.thumbnail((1000, 1000))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=70, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def show_hero():
    path = find_banner()
    data = ""
    if path:
        data = encode_background(str(path), path.stat().st_mtime)
        if data:
            st.markdown(BG_CSS % data, unsafe_allow_html=True)
    st.markdown(TEXT_HERO, unsafe_allow_html=True)
    if not data:
        st.caption("عکس پس‌زمینه پیدا نشد. یک عکس png یا jpg آپلود کو.")
