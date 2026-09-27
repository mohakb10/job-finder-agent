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
company, title, location, apply_url, posting_source, description, fit_score, fit_reasoning

apply_url may be null if you couldn't find a direct link -- in that case set
posting_source to something a human could use to find it themselves (e.g.
"Greenhouse - search 'CompanyName Senior Data Scientist'").
"""


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


def search_jobs(extra_instructions: str = None, max_searches: int = 12) -> list:
    """
    Run the search agent and return a list of scored job-suggestion dicts.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    profile = load_profile()

    user_msg = "Find and score currently-open postings matching this profile."
    if extra_instructions:
        user_msg += f"\n\nAdditional instructions for this run: {extra_instructions}"

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT.format(profile=json.dumps(profile, indent=2)),
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}],
        messages=[{"role": "user", "content": user_msg}],
    )

    log_usage("search_agent", CLAUDE_MODEL, response.usage)

    final_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return _extract_json_array(final_text)
