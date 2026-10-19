from datetime import datetime

import streamlit as st

from src.agents.analyst_agent import is_eligible_for_analysis, run_analysis
from src.config import OUTPUT_DIR
from src.db import list_jobs
from src.services import SUBMITTED_STATUSES
from src.ui.common import require_api_key

REPORT_PATH = OUTPUT_DIR / "last_analysis.md"


def render():
    st.title("What is working")
    st.markdown(
        '<p class="lede">Claude reads your whole application history and points out patterns: '
        "what the roles that replied have in common, what keeps going quiet, and what to change "
        "next. It uses the larger model, so run it when you have something new to learn from.</p>",
        unsafe_allow_html=True,
    )

    jobs = list_jobs()
    submitted = sum(1 for j in jobs if j["status"] in SUBMITTED_STATUSES)
    interviews = sum(1 for j in jobs if j["status"] in ("interview", "offer"))
    eligible = is_eligible_for_analysis()

    if eligible:
        st.info("You have {} applications and {} at interview or offer, enough to look for patterns.".format(submitted, interviews))
        go = True
    else:
        st.info(
            "It works best after your first interview or about 10 applications. "
            "You have {} so far.".format(submitted)
        )
        go = st.checkbox("Run it anyway")

    if st.button("Run analysis", type="primary", disabled=not go):
        if require_api_key():
            with st.spinner("Reading your pipeline..."):
                try:
                    report = run_analysis()
                    REPORT_PATH.write_text(report, encoding="utf-8")
                except Exception as e:
                    st.error("The analysis failed: {}".format(e))

    if REPORT_PATH.exists():
        stamp = datetime.fromtimestamp(REPORT_PATH.stat().st_mtime).strftime("%b %d at %I:%M %p")
        st.subheader("Latest report")
        st.caption("Run on {}".format(stamp))
        st.markdown(REPORT_PATH.read_text(encoding="utf-8"))
