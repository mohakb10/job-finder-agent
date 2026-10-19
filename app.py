"""
Streamlit front end for the job finder.

Run with:  streamlit run app.py
Uses the same database and agents as the CLI, so you can mix the two.
"""
import streamlit as st

from src.db import init_db
from src.ui import analyst, dashboard, pipeline, search, theme
from src.ui.common import setup_checks

st.set_page_config(page_title="Job search", layout="wide")
theme.inject_css()
init_db()

PAGES = {
    "Dashboard": dashboard.render,
    "Pipeline": pipeline.render,
    "Search": search.render,
    "Analyst": analyst.render,
}

if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"

with st.sidebar:
    st.markdown("### Job finder")
    st.radio("Go to", list(PAGES), key="page", label_visibility="collapsed")
    st.write("")
    problems = [msg for ok, msg in setup_checks() if not ok]
    if problems:
        with st.expander("Setup needs attention", expanded=True):
            for msg in problems:
                st.markdown("- {}".format(msg))
    else:
        st.caption("Setup complete: API key and data files found.")

PAGES[st.session_state["page"]]()
