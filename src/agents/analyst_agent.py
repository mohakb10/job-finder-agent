"""
Pipeline Analyst
----------------
An occasional, high-level pass over your entire application history that
surfaces what's actually correlating with interviews vs. what's wasting
time. Meant to be run periodically (e.g. after every ~10 applications or
whenever you get a new interview), not on every job. Never edits anything
itself -- it just writes a report for you to read.
"""
import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_ANALYST_MODEL, load_profile
from src.db import list_jobs, log_usage

SYSTEM_PROMPT = """You are analyzing a job seeker's application pipeline to find
patterns correlating with success (interviews/offers) vs. wasted effort
(rejections, silence). Be specific and actionable -- reference actual
companies/titles from the data, not generic advice.

Candidate's target profile:
{profile}

Full pipeline history (JSON):
{jobs}

Write a short report covering:
1. What's working -- what do the roles that got interviews/offers have in
   common (domain, title level, company size/stage, source, etc.)?
2. What's not working -- what pattern shows up in rejections or long silence?
3. 2-3 concrete adjustments to search criteria, targeting, or the resume
   emphasis strategy for the next batch of applications.

Keep it under 400 words. If there isn't enough data yet for a pattern, say
so plainly rather than overreaching from a handful of data points.
"""


def is_eligible_for_analysis(min_new_applications: int = 10) -> bool:
    jobs = list_jobs()
    has_new_interview = any(j["status"] == "interview" for j in jobs)
    applied_count = sum(1 for j in jobs if j["status"] in ("applied", "interview", "offer", "rejected"))
    return has_new_interview or applied_count >= min_new_applications


def run_analysis() -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    profile = load_profile()
    jobs = list_jobs()

    import json

    response = client.messages.create(
        model=CLAUDE_ANALYST_MODEL,
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": SYSTEM_PROMPT.format(
                    profile=json.dumps(profile, indent=2),
                    jobs=json.dumps(jobs, indent=2, default=str),
                ),
            }
        ],
    )
    log_usage("pipeline_analyst", CLAUDE_ANALYST_MODEL, response.usage)

    return "\n".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ).strip()
