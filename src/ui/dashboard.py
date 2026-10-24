import html
from collections import Counter
from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st

from src.db import get_usage_summary, list_jobs
from src.services import SUBMITTED_STATUSES
from src.ui.common import days_since, go_to_job, go_to_page, parse_ts
from src.ui.theme import job_line, pipeline_strip

ACCENT = "#0B7A75"
FOLLOW_UP_AFTER_DAYS = 14


def _plural(n, word):
    return "{} {}{}".format(n, word, "" if n == 1 else "s")


def _summary_sentence(counts, submitted):
    waiting = counts.get("discovered", 0)
    in_interviews = counts.get("interview", 0) + counts.get("offer", 0)
    parts = []
    if submitted:
        parts.append("{} sent".format(_plural(submitted, "application")))
        if in_interviews:
            parts[-1] += ", {} at interview or offer".format(in_interviews)
    if waiting:
        parts.append("{} waiting for your review".format(_plural(waiting, "posting")))
    if not parts:
        return "You have jobs saved, but nothing is waiting on you right now."
    return ". ".join(p[0].upper() + p[1:] for p in parts) + "."


def render():
    st.title("Job search")

    jobs = list_jobs()
    if not jobs:
        st.markdown(
            '<p class="lede">Your pipeline is empty. Run a search and the best matches for '
            "your profile will show up here, scored and ready to review.</p>",
            unsafe_allow_html=True,
        )
        st.button("Run your first search", type="primary", on_click=go_to_page, args=("Search",))
        return

    counts = Counter(j["status"] for j in jobs)
    submitted_jobs = [j for j in jobs if j["status"] in SUBMITTED_STATUSES]
    submitted = len(submitted_jobs)

    st.markdown('<p class="lede">{}</p>'.format(html.escape(_summary_sentence(counts, submitted))), unsafe_allow_html=True)

    pipeline_strip(counts)
    closed = ["{} {}".format(counts[s], s) for s in ["rejected", "skipped", "withdrawn"] if counts.get(s)]
    if closed:
        st.markdown('<div class="pipe-foot">Closed out: {}.</div>'.format(", ".join(closed)), unsafe_allow_html=True)
    else:
        st.markdown('<div class="pipe-foot"></div>', unsafe_allow_html=True)

    # Headline numbers
    reached_interview = counts.get("interview", 0) + counts.get("offer", 0)
    scored_applied = [j["fit_score"] for j in submitted_jobs if j.get("fit_score") is not None]
    k1, k2, k3 = st.columns(3)
    k1.metric("Applications sent", submitted)
    k2.metric(
        "Interview rate",
        "{:.0f}%".format(100.0 * reached_interview / submitted) if submitted else "none yet",
        help="Share of your submitted applications that reached an interview or offer.",
    )
    k3.metric(
        "Average fit of what you applied to",
        "{:.0f}".format(sum(scored_applied) / len(scored_applied)) if scored_applied else "none yet",
        help="Average of the 0 to 100 fit scores for postings you submitted.",
    )

    st.write("")
    left, right = st.columns(2, gap="large")

    with left:
        st.subheader("Waiting for your review")
        waiting = [j for j in jobs if j["status"] == "discovered"]
        if not waiting:
            st.markdown(
                '<p class="muted">Nothing to review. Run a search to bring in new postings.</p>',
                unsafe_allow_html=True,
            )
            st.button("Go to search", on_click=go_to_page, args=("Search",), key="dash_to_search")
        for job in waiting[:5]:
            c1, c2 = st.columns([3, 1])
            where = job.get("location") or "Location not listed"
            c1.markdown(job_line(job, html.escape(where)), unsafe_allow_html=True)
            c2.button("Open", key="dash_open_{}".format(job["id"]), on_click=go_to_job, args=(job["id"],))
        if len(waiting) > 5:
            st.button(
                "Review all {}".format(len(waiting)),
                on_click=go_to_page,
                args=("Search",),
                key="dash_review_all",
            )

    with right:
        st.subheader("Time to follow up")
        overdue = []
        for job in jobs:
            if job["status"] != "applied":
                continue
            d = days_since(job.get("applied_at"))
            if d is not None and d >= FOLLOW_UP_AFTER_DAYS:
                overdue.append((d, job))
        overdue.sort(key=lambda x: -x[0])
        if not overdue:
            st.markdown(
                '<p class="muted">Nothing overdue. Applications with no news after {} days will '
                "show up here.</p>".format(FOLLOW_UP_AFTER_DAYS),
                unsafe_allow_html=True,
            )
        for d, job in overdue[:5]:
            c1, c2 = st.columns([3, 1])
            c1.markdown(
                job_line(job, '<span class="late">Applied {} days ago</span>'.format(d)),
                unsafe_allow_html=True,
            )
            c2.button("Open", key="dash_fu_{}".format(job["id"]), on_click=go_to_job, args=(job["id"],))

    st.write("")
    ch1, ch2 = st.columns(2, gap="large")

    with ch1:
        st.subheader("Applications per week")
        stamps = [parse_ts(j.get("applied_at")) for j in submitted_jobs]
        stamps = [t for t in stamps if t is not None]
        if not stamps:
            st.markdown(
                '<p class="muted">No applications logged yet. Mark a job as applied and the weekly '
                "count starts here.</p>",
                unsafe_allow_html=True,
            )
        else:
            weeks = Counter((t - timedelta(days=t.weekday())).date() for t in stamps)
            df = pd.DataFrame(
                {"week": [pd.Timestamp(w) for w in weeks], "applications": list(weeks.values())}
            )
            # Whole-number ticks only: list them out while the counts are small.
            most = max(weeks.values())
            tick_values = list(range(0, most + 1)) if most <= 12 else None
            chart = (
                alt.Chart(df)
                .mark_bar(color=ACCENT, size=26)
                .encode(
                    x=alt.X("week:T", title=None, axis=alt.Axis(format="%b %d")),
                    y=alt.Y(
                        "applications:Q",
                        title=None,
                        axis=alt.Axis(tickMinStep=1, values=tick_values),
                    ),
                    tooltip=[alt.Tooltip("week:T", title="Week of", format="%b %d"), "applications:Q"],
                )
                .properties(height=220)
            )
            st.altair_chart(chart, use_container_width=True)

    with ch2:
        st.subheader("How well postings fit you")
        scores = [j["fit_score"] for j in jobs if j.get("fit_score") is not None]
        if not scores:
            st.markdown('<p class="muted">Fit scores appear after your first search.</p>', unsafe_allow_html=True)
        else:
            df = pd.DataFrame({"fit": scores})
            chart = (
                alt.Chart(df)
                .mark_bar(color=ACCENT)
                .encode(
                    x=alt.X("fit:Q", bin=alt.Bin(step=10, extent=[0, 100]), title="Fit score"),
                    y=alt.Y("count()", title=None, axis=alt.Axis(tickMinStep=1)),
                )
                .properties(height=220)
            )
            st.altair_chart(chart, use_container_width=True)

    usage = get_usage_summary()
    if usage["calls"]:
        st.caption(
            "Claude usage so far: {} calls, {:,} input and {:,} output tokens.".format(
                usage["calls"], usage["input_tokens"], usage["output_tokens"]
            )
        )
