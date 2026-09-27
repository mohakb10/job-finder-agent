"""
Resume Tailoring Agent
----------------------
Given a job description, decides:
  - which bullets to include under each job/project (from the fixed inventory)
  - what order to put them in
  - which pre-approved phrasing variant of each bullet to use

It can NEVER invent a new bullet, edit a number, or write freeform text --
every bullet id and variant text returned by the model is re-validated
against the source-of-truth resume_bullets.json before anything is rendered.
If the model returns anything not found in the allowed set, that section
falls back to the default bullet order/phrasing.
"""
import json
import re

import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, load_resume
from src.db import log_usage

SYSTEM_PROMPT = """You are tailoring a resume for a specific job posting.

You may ONLY do two things per section (Vectra AI experience, Meta experience,
Capstone project):
1. Reorder the bullets within that section (you may not move bullets between
   sections, and you may not add or remove bullets -- all bullets for a
   section must appear exactly once).
2. For each bullet, choose ONE version of its text: either "default" or one
   of its "variants" -- verbatim, no edits.

You must NOT invent new bullets, new numbers, new claims, or edit the
wording of a chosen version in any way. Pick the ordering and phrasing that
best emphasizes relevance to the target job description below.

Job description:
{job_description}

Resume bullet inventory (JSON):
{resume_json}

Respond with ONLY JSON (no markdown fences, no other text) in this exact shape:
{{
  "vectra_order": ["<bullet_id>", ...all 5 vectra bullet ids in your chosen order...],
  "vectra_text_choice": {{"<bullet_id>": "default_or_variant_text_chosen_verbatim", ...}},
  "meta_order": ["<bullet_id>", ...all 3 meta bullet ids...],
  "meta_text_choice": {{"<bullet_id>": "...", ...}},
  "capstone_order": ["<bullet_id>", ...all 2 capstone bullet ids...],
  "capstone_text_choice": {{"<bullet_id>": "...", ...}},
  "summary_of_emphasis": "1-2 sentences on what you emphasized and why"
}}
"""


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
    if not match:
        raise ValueError(f"Could not find JSON object in model output:\n{text[:500]}")
    return json.loads(match.group(0))


def _validate_section(section: dict, chosen_order: list, chosen_text: dict) -> list:
    """
    Returns a validated, ordered list of (bullet_id, text) tuples for a
    section. Falls back to default order/text for anything the model got
    wrong so a bad response degrades gracefully instead of corrupting the
    resume.
    """
    bullets_by_id = {b["id"]: b for b in section["bullets"]}
    valid_ids = set(bullets_by_id.keys())

    order = [bid for bid in chosen_order if bid in valid_ids]
    # Add back any missing ids (in default order) so nothing gets silently dropped
    for bid in bullets_by_id:
        if bid not in order:
            order.append(bid)

    result = []
    for bid in order:
        bullet = bullets_by_id[bid]
        allowed_texts = {bullet["default"]} | set(bullet.get("variants", []))
        candidate_text = chosen_text.get(bid, bullet["default"])
        text = candidate_text if candidate_text in allowed_texts else bullet["default"]
        result.append({"id": bid, "text": text})
    return result


def tailor_resume(job_description: str) -> dict:
    """
    Returns a dict with validated section orderings/text plus the model's
    stated emphasis rationale, ready to hand to the PDF renderer.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resume = load_resume()

    vectra_section = next(e for e in resume["experience"] if e["id"] == "vectra")
    meta_section = next(e for e in resume["experience"] if e["id"] == "meta")
    capstone_section = resume["projects"][0]

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": SYSTEM_PROMPT.format(
                    job_description=job_description,
                    resume_json=json.dumps(resume, indent=2),
                ),
            }
        ],
    )
    log_usage("tailor_agent", CLAUDE_MODEL, response.usage)

    text = "\n".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    )
    raw = _extract_json(text)

    validated = {
        "vectra": _validate_section(
            vectra_section, raw.get("vectra_order", []), raw.get("vectra_text_choice", {})
        ),
        "meta": _validate_section(
            meta_section, raw.get("meta_order", []), raw.get("meta_text_choice", {})
        ),
        "capstone": _validate_section(
            capstone_section,
            raw.get("capstone_order", []),
            raw.get("capstone_text_choice", {}),
        ),
        "summary_of_emphasis": raw.get("summary_of_emphasis", ""),
    }
    return validated
