"""
Job Search Agent
----------------
Uses Claude with the web_search tool to discover currently-open postings
matching the candidate's profile, then scores each one for fit.

Nothing here writes to the `jobs` table directly with an "approved" status --
results are returned as suggestions for the CLI to display, and the human
decides what to promote into the pipeline. Duplicate detection against
existing jobs happens in the CLI layer.
"""
import json
import re

import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, load_profile
from src.db import log_usage

SYSTEM_PROMPT = """You are a job search research assistant for a specific candidate.
You have access to web search. Your job: find CURRENTLY OPEN job postings that
genuinely match the candidate's profile below, then score each one for fit.

Candidate profile:
{profile}

Hard requirements (a posting that fails either one must be discarded, not scored):
A. LOCATION. The role must be one of:
   - based in the New York City area, or
   - based in the San Francisco Bay Area, or
   - remote or hybrid-flexible, but ONLY at a company that has a real office in
     NYC or the SF Bay Area (e.g. Stripe, Datadog, Databricks). Confirm the
     office exists; do not assume it. Remote-only companies with no NYC/SF
     office do not qualify.
   Set location_match to "nyc", "sf", or "remote_with_office" accordingly.
B. EXPERIENCE. The candidate has {years} years of experience. Read the posting
   for the stated minimum years of experience and put it in years_required
   (a number). Discard anything requiring more than {max_years} years. If the
   posting states no number, set years_required to null and keep it only if the
   title and responsibilities are mid-level or senior-IC rather than staff,
   principal or management. Treat "5+ years" as 5, and "4-6 years" as 4.

Process:
1. Run several distinct web searches (vary the phrasing / site, e.g. try
   company career pages, Greenhouse/Lever boards, LinkedIn) to find real,
   currently-open postings. Do not rely on memory -- only report postings
   you actually found via search in this conversation.
2. For each posting, note: company, exact title, location, a direct apply
   URL if you found one, and a short (2-3 sentence) description of the role
   based on what you read.
3. Score each posting 0-100 for fit against the candidate's target criteria,
   and write 1-2 sentences of reasoning for the score. Weight domain match
   (security/anomaly detection/identity is a strong plus per the profile),
   seniority match, and whether the role is applied/production ML vs. pure
   analytics or pure research.
4. Discard postings that are clearly a bad fit (e.g. junior analyst roles,
   roles requiring a PhD in an unrelated field, roles with no ML component).
5. Aim for 8-15 good candidates across your searches, fewer is fine if you
   can't find good matches -- do not pad with weak fits just to hit a count.

When you are done searching, respond with ONLY a JSON array (no markdown
fences, no other text) of objects with exactly these keys:
company, title, location, location_match, years_required, apply_url, posting_source, description, fit_score, fit_reasoning

apply_url may be null if you couldn't find a direct link -- in that case set
posting_source to something a human could use to find it themselves (e.g.
"Greenhouse - search 'CompanyName Senior Data Scientist'").
"""


DEFAULT_MAX_YEARS = 4
ALLOWED_LOCATION_MATCHES = {"nyc", "sf", "remote_with_office"}


def filter_suggestions(jobs: list, max_years: int = DEFAULT_MAX_YEARS) -> tuple:
    """Enforce the hard requirements in code instead of trusting the model.

    Returns (kept, dropped_location, dropped_experience).
    """
    kept, dropped_location, dropped_experience = [], 0, 0
    for job in jobs:
        if str(job.get("location_match", "")).lower() not in ALLOWED_LOCATION_MATCHES:
            dropped_location += 1
            continue
        years = job.get("years_required")
        if isinstance(years, (int, float)) and years > max_years:
            dropped_experience += 1
            continue
        kept.append(job)
    return kept, dropped_location, dropped_experience


def _extract_json_array(text: str) -> list:
    text = text.strip()
    # Strip markdown fences if the model added them anyway
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    text = text.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find a JSON array in model output:\n{text[:500]}")
    return json.loads(match.group(0))


def search_jobs(extra_instructions: str = None, max_searches: int = 12) -> tuple:
    """
    Run the search agent. Returns (suggestions, dropped_location, dropped_experience)
    where suggestions already passed the location and experience filters.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    profile = load_profile()
    max_years = profile.get("target", {}).get("max_years_required", DEFAULT_MAX_YEARS)

    user_msg = "Find and score currently-open postings matching this profile."
    if extra_instructions:
        user_msg += f"\n\nAdditional instructions for this run: {extra_instructions}"

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT.format(
            profile=json.dumps(profile, indent=2),
            years=profile.get("years_experience", "several"),
            max_years=max_years,
        ),
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}],
        messages=[{"role": "user", "content": user_msg}],
    )

    log_usage("search_agent", CLAUDE_MODEL, response.usage)

    final_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return filter_suggestions(_extract_json_array(final_text), max_years)
