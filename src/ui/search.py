import html

import streamlit as st

from src.config import load_profile
from src.db import list_jobs, update_job_status
from src.services import run_search
from src.ui.common import go_to_job, rerun, require_api_key
from src.ui.theme import job_line


def _profile_summary():
    try:
        target = load_profile().get("target", {})
    except FileNotFoundError as e:
        st.warning(str(e))
        return
    titles = ", ".join(target.get("titles", [])) or "no titles set"
    places = ", ".join(target.get("locations", [])) or "no locations set"
    st.caption(
        "Searching for {} in {}. Change this in data/profile.seed.json.".format(titles, places)
    )


def render():
    st.title("Search")
    st.markdown(
        '<p class="lede">Claude searches the web for open roles that match your profile and '
        "scores each one. Nothing is applied for automatically, and new roles land in your "
        "review queue below.</p>",
        unsafe_allow_html=True,
    )
    _profile_summary()

    notes = st.text_input(
        "Anything specific this time?",
        placeholder="For example: focus on fraud and trust and safety teams at larger companies",
    )
    max_searches = st.slider(
        "How many web searches",
        min_value=4,
        max_value=20,
        value=12,
        help="More searches finds more roles but takes longer and costs more.",
    )

    if st.button("Run search", type="primary"):
        if require_api_key():
            with st.spinner("Searching the web. This usually takes a minute or two."):
                try:
                    added, skipped, malformed = run_search(
                        notes=notes.strip() or None, max_searches=max_searches
                    )
                    st.session_state["last_search"] = (added, skipped, malformed)
                except ValueError:
                    st.session_state.pop("last_search", None)
                    st.error(
                        "The search finished, but the results could not be read. "
                        "Run it again, and if it keeps happening, try fewer searches."
                    )
                except Exception as e:
                    st.session_state.pop("last_search", None)
                    st.error("The search failed: {}".format(e))

    last = st.session_state.get("last_search")
    if last:
        added, skipped, malformed = last
        msg = "Added {} new role{}".format(added, "" if added == 1 else "s")
        if skipped:
            msg += ", skipped {} you already have".format(skipped)
        if malformed:
            msg += ", ignored {} with missing details".format(malformed)
        st.success(msg + ".")

    st.write("")
    queue = [j for j in list_jobs() if j["status"] == "discovered"]
    st.subheader("Review queue ({})".format(len(queue)))
    if not queue:
        st.markdown(
            '<p class="muted">Nothing waiting. Run a search and new roles will appear here, '
            "highest fit first.</p>",
            unsafe_allow_html=True,
        )
        return

    for job in queue:
        with st.container(border=True):
            where = job.get("location") or "Location not listed"
            st.markdown(job_line(job, html.escape(where)), unsafe_allow_html=True)
            if job.get("fit_reasoning"):
                st.write(job["fit_reasoning"])
            c1, c2, c3, c4, _ = st.columns([1.2, 1, 1, 1.4, 4])
            if c1.button("Approve", type="primary", key="q_ok_{}".format(job["id"])):
                update_job_status(job["id"], "approved")
                rerun()
            if c2.button("Skip", key="q_skip_{}".format(job["id"])):
                update_job_status(job["id"], "skipped")
                rerun()
            c3.button("Open", key="q_open_{}".format(job["id"]), on_click=go_to_job, args=(job["id"],))
            if job.get("apply_url"):
                c4.link_button("Posting", job["apply_url"])
