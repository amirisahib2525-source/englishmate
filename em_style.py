"""EnglishMate look and feel: dark blue + light blue palette."""
import html
import json

import streamlit as st

try:
    import streamlit.components.v1 as components
except Exception:  # pragma: no cover
    components = None

CSS = """
<style>
:root {--bg:#0a1a3f; --card:#12285c; --line:#27479a; --text:#f4f8ff;
  --muted:#b8c8ee; --blue:#4da3ff; --blue2:#7cc4ff; --ok:#33c27f;
  --bad:#ff6b6b; --green:#7ddc9a;}
.block-container {max-width:920px; padding:1rem 1rem 4rem 1rem;}
[data-testid="stMain"] .block-container {direction:rtl; text-align:right;}
h1,h2,h3,h4 {color:var(--text);}
.hero {background:linear-gradient(135deg,#123a8f 0%,#2f7de1 100%);
  border-radius:20px; padding:20px 16px; text-align:center;
  margin-bottom:14px; border:1px solid var(--line);}
.hero h1 {color:#fff; margin:0; font-size:1.8rem;}
.hero p {color:#dbe9ff; margin:6px 0 0 0;}
.card {background:var(--card); color:var(--text);
  border:1px solid var(--line); border-radius:16px;
  padding:14px 16px; margin:10px 0;}
.card.ok {border-right:6px solid var(--ok);}
.card.bad {border-right:6px solid var(--bad);}
.card.q {background:#17357a; font-size:1.15rem; font-weight:600;}
.card.tip {border-right:6px solid var(--blue);}
.ltr {direction:ltr; text-align:left;}
.rtl {direction:rtl; text-align:right;}
.word {font-size:1.3rem; font-weight:700; color:#fff;}
.mean {color:var(--blue2); font-weight:600; margin-top:2px;}
.ex {color:var(--muted); font-size:.95rem;}
.badge {display:inline-block; background:#1d4fb3; color:#fff;
  border-radius:999px; padding:2px 10px; font-size:.8rem; margin:0 4px;}
.chip {display:inline-block; background:#1c3a85; color:#fff;
  border-radius:999px; padding:4px 12px; margin:3px; font-size:.9rem;}
.opt {background:var(--card); color:var(--text);
  border:1.5px solid var(--line); border-radius:12px;
  padding:10px 14px; margin:6px 0;}
.opt.right {background:#124a3a; border-color:var(--ok);}
.opt.wrong {background:#5a1f2e; border-color:var(--bad);}
.score {font-size:3rem; font-weight:800; text-align:center;
  color:var(--blue2); margin:0;}
.formula {background:#0d2250; border:1px dashed var(--blue);
  border-radius:12px; padding:10px 12px; margin:6px 0;
  direction:ltr; text-align:left; color:#fff;}
.stButton > button {width:100%; border-radius:12px; font-weight:600;
  min-height:46px; background:#1d4fb3; color:#fff;
  border:1px solid var(--blue);}
.stButton > button:hover {background:#2f7de1; border-color:var(--blue2);}
[data-testid="stMetric"] {background:var(--card);
  border:1px solid var(--line); border-radius:14px; padding:10px 14px;}
div[data-baseweb="input"], div[data-baseweb="base-input"],
div[data-baseweb="textarea"], div[data-baseweb="select"] > div
{border-radius:12px;}
div[data-baseweb="input"]:focus-within,
div[data-baseweb="base-input"]:focus-within,
div[data-baseweb="textarea"]:focus-within,
div[data-baseweb="select"]:focus-within > div
{border-color:var(--green) !important;
  box-shadow:0 0 0 1px var(--green) !important;}
[data-testid="InputInstructions"] {display:none !important;}
.st-key-navbox div[role="radiogroup"] {display:grid;
  grid-template-columns:repeat(3,1fr); gap:8px; width:100%;}
.st-key-navbox label {background:var(--card); border:1px solid var(--line);
  border-radius:12px; padding:10px 6px; margin:0; cursor:pointer;
  justify-content:center; text-align:center;}
.st-key-navbox label > div:first-child {display:none;}
.st-key-navbox label:has(input:checked) {background:#2f7de1;
  border-color:var(--blue2);}
@media (min-width:760px) {
  .st-key-navbox div[role="radiogroup"] {grid-template-columns:repeat(6,1fr);}
}
</style>
"""


def esc(x):
    return html.escape(str(x))


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def card(inner, cls=""):
    st.markdown(f'<div class="card {cls}">{inner}</div>',
                unsafe_allow_html=True)


def chips(items):
    return "".join(f'<span class="chip ltr">{esc(i)}</span>' for i in items)


def speak_button(word):
    """Pronunciation with the browser's built-in voice (if available)."""
    if components is None:
        return
    js = (f"var u=new SpeechSynthesisUtterance({json.dumps(str(word))});"
          "u.lang='en-US';u.rate=0.85;speechSynthesis.cancel();"
          "speechSynthesis.speak(u);")
    style = ("background:#1d4fb3;color:#fff;border:1px solid #4da3ff;"
             "border-radius:12px;padding:10px;font-size:16px;width:100%;"
             "cursor:pointer;")
    btn = (f'<button onclick="{html.escape(js, quote=True)}" '
           f'style="{style}">🔊 تلفظ</button>')
    try:
        components.html(btn, height=50)
    except Exception:
        pass
