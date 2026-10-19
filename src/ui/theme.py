"""
Visual identity for the app.

Palette (named so it is easy to change in one place):
  mist   #F3F5F7  page background
  paper  #FFFFFF  panels, sidebar
  ink    #172033  text
  slate  #5B6577  secondary text
  rule   #DDE2E8  hairlines
  teal   #0B7A75  primary action and the pipeline strip
  amber  #B7791F  things that need attention (follow-ups)

The one memorable element is the pipeline strip on the dashboard: your whole
search as a single bar that gets darker as postings move toward an offer.
"""
import html

import streamlit as st

from src.ui.common import STATUS_LABELS

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap');

html, body, [class*="st-"], .stMarkdown, button, input, textarea {
  font-family: 'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif;
}
.block-container { padding-top: 2.2rem; max-width: 1180px; }
h1 { font-size: 1.85rem !important; font-weight: 600 !important; letter-spacing: -0.012em; }
h2, h3 { font-weight: 600 !important; letter-spacing: -0.006em; }
footer { visibility: hidden; }

section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #DDE2E8; }

.lede { color: #5B6577; font-size: 1.05rem; line-height: 1.5; margin: -0.4rem 0 1.4rem 0; max-width: 62ch; }
.muted { color: #5B6577; font-size: 0.92rem; }

/* pipeline strip */
.pipe { display: flex; gap: 3px; margin: 0.4rem 0 0.5rem 0; }
.pipe .stage {
  min-width: 0; padding: 0.85rem 1rem 0.8rem 1rem;
  display: flex; flex-direction: column; gap: 0.15rem; color: #172033;
}
.pipe .stage:first-child { border-radius: 10px 0 0 10px; }
.pipe .stage:last-child { border-radius: 0 10px 10px 0; }
.pipe .n { font-size: 2rem; font-weight: 600; line-height: 1.05; font-variant-numeric: tabular-nums; }
.pipe .l { font-size: 0.88rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pipe .s-discovered { background: #D5EAE8; }
.pipe .s-approved   { background: #A8D5D1; }
.pipe .s-applied    { background: #5DB0AA; }
.pipe .s-interview  { background: #167F78; color: #FFFFFF; }
.pipe .s-offer      { background: #0B5E5A; color: #FFFFFF; }
.pipe-foot { color: #5B6577; font-size: 0.9rem; margin-bottom: 1.6rem; }

/* job rows on the dashboard */
.jobline { padding: 0.15rem 0 0.1rem 0; line-height: 1.35; }
.jobline .co { font-weight: 600; }
.jobline .sub { color: #5B6577; font-size: 0.88rem; }
.fit { display: inline-block; min-width: 2.1rem; text-align: center; font-weight: 600;
       font-size: 0.85rem; border-radius: 6px; padding: 0.05rem 0.4rem; background: #D5EAE8; color: #0B3F3C; }
.fit.low { background: #ECEFF3; color: #5B6577; }
.late { color: #B7791F; font-weight: 500; }
</style>
"""

STAGE_ORDER = ["discovered", "approved", "applied", "interview", "offer"]


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def pipeline_strip(counts):
    """Render the five-stage strip. `counts` maps status -> number of jobs."""
    cells = []
    for stage in STAGE_ORDER:
        n = counts.get(stage, 0)
        # Grow with the count, but never let an empty stage disappear.
        cells.append(
            '<div class="stage s-{stage}" style="flex: {grow} 1 0">'
            '<span class="n">{n}</span><span class="l">{label}</span></div>'.format(
                stage=stage, grow=1 + n, n=n, label=STATUS_LABELS[stage]
            )
        )
    st.markdown('<div class="pipe">{}</div>'.format("".join(cells)), unsafe_allow_html=True)


def fit_badge(score):
    if score is None:
        return '<span class="fit low">n/a</span>'
    cls = "fit" if score >= 70 else "fit low"
    return '<span class="{}">{}</span>'.format(cls, int(score))


def job_line(job, sub):
    """One compact job row: fit badge, company, title, and a sub line (already safe HTML)."""
    return (
        '<div class="jobline">{badge} <span class="co">{company}</span>, {title}'
        '<div class="sub">{sub}</div></div>'
    ).format(
        badge=fit_badge(job.get("fit_score")),
        company=html.escape(job["company"]),
        title=html.escape(job["title"]),
        sub=sub,
    )
