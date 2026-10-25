import streamlit as st

st.set_page_config(page_title="EnglishMate AI", page_icon="📘")

try:
    import em_ui
    em_ui.main()
except Exception as exc:
    if type(exc).__name__ in ("RerunException", "StopException"):
        raise
    st.error("خطایی رخ داد. عکس این پیام را برای پشتیبان بفرست:")
    st.exception(exc)
