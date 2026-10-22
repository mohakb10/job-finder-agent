"""
Resume Tailoring Agent
----------------------
Given a job description, decides, for every experience and project entry in
your resume file:
  - what order to put its bullets in
  - which pre-approved phrasing variant of each bullet to use

It can NEVER invent a new bullet, edit a number, or write freeform text --
every bullet id and variant text returned by the model is re-validated
against the source-of-truth resume_bullets.seed.json before anything is
rendered. If the model returns anything not found in the allowed set, that
section falls back to the default bullet order/phrasing.

Sections are read from the resume file, so adding a job or project, or
changing how many bullets one has, needs no code changes.
"""
import json
import re

import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, load_resume
from src.db import log_usage

SYSTEM_PROMPT = """You are tailoring a resume for a specific job posting.

The resume has several sections (jobs and projects), listed in the inventory
below. You may ONLY do two things per section:
1. Reorder the bullets within that section. You may not move bullets between
   sections, and you may not add or remove bullets: every bullet of a
   section must appear exactly once.
2. For each bullet, choose ONE version of its text: either its "default" or
   one of its "variants", copied verbatim, no edits.

You must NOT invent new bullets, new numbers, new claims, or edit the
wording of a chosen version in any way. Pick the ordering and phrasing that
best emphasizes relevance to the target job description below.

Job description:
{job_description}

Resume inventory (JSON). Each section has an "id" and a list of bullets:
{resume_json}

Sections and how many bullets each must contain in your answer:
{section_summary}

Respond with ONLY JSON (no markdown fences, no other text) in this exact shape:
{{
  "sections": {{
    "<section_id>": {{
      "order": ["<bullet_id>", "..."],
      "text_choice": {{"<bullet_id>": "<default or variant text, verbatim>"}}
    }}
  }},
  "summary_of_emphasis": "1-2 sentences on what you emphasized and why"
}}
Include every section id listed above.
"""


def resume_sections(resume: dict) -> list:
    """Every experience and project entry, in the order they appear on the resume."""
    return list(resume.get("experience", [])) + list(resume.get("projects", []))


def default_sections(resume: dict) -> dict:
    """The untailored resume: every section in its file order with default text."""
    return {
        s["id"]: [{"id": b["id"], "text": b["default"]} for b in s["bullets"]]
        for s in resume_sections(resume)
    }


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
    if not match:
        raise ValueError(f"Could not find JSON object in model output:\n{text[:500]}")
    return json.loads(match.group(0))


def _validate_section(section: dict, chosen_order: list, chosen_text: dict) -> list:
    """
    Returns a validated, ordered list of {"id", "text"} dicts for a section.
    Falls back to default order/text for anything the model got wrong so a
    bad response degrades gracefully instead of corrupting the resume.
    """
    bullets_by_id = {b["id"]: b for b in section["bullets"]}

    order = []
    for bid in chosen_order if isinstance(chosen_order, list) else []:
        # Ignore unknown ids and repeats.
        if bid in bullets_by_id and bid not in order:
            order.append(bid)
    # Add back any missing ids (in default order) so nothing gets silently dropped
    for bid in bullets_by_id:
        if bid not in order:
            order.append(bid)

    if not isinstance(chosen_text, dict):
        chosen_text = {}
    result = []
    for bid in order:
        bullet = bullets_by_id[bid]
        allowed_texts = {bullet["default"]} | set(bullet.get("variants", []))
        candidate_text = chosen_text.get(bid, bullet["default"])
        text = candidate_text if candidate_text in allowed_texts else bullet["default"]
        result.append({"id": bid, "text": text})
    return result


def validate_tailoring(resume: dict, raw: dict) -> dict:
    """Turn a raw model answer into a safe {"sections": ..., "summary_of_emphasis": ...}."""
    raw_sections = raw.get("sections") if isinstance(raw.get("sections"), dict) else {}
    sections = {}
    for section in resume_sections(resume):
        choice = raw_sections.get(section["id"])
        choice = choice if isinstance(choice, dict) else {}
        sections[section["id"]] = _validate_section(
            section, choice.get("order", []), choice.get("text_choice", {})
        )
    return {"sections": sections, "summary_of_emphasis": str(raw.get("summary_of_emphasis", ""))}


def tailor_resume(job_description: str) -> dict:
    """
    Returns {"sections": {section_id: [{"id", "text"}, ...]}, "summary_of_emphasis": str},
    ready to hand to the PDF renderer.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resume = load_resume()

    # Only the sections the agent may reorder go to the model, not your contact details.
    inventory = {
        "experience": resume.get("experience", []),
        "projects": resume.get("projects", []),
    }
    section_summary = "\n".join(
        '- "{}" ({}): {} bullet{}'.format(
            s["id"], s.get("company") or s.get("name"), len(s["bullets"]), "" if len(s["bullets"]) == 1 else "s"
        )
        for s in resume_sections(resume)
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=3000,
        messages=[
            {
                "role": "user",
                "content": SYSTEM_PROMPT.format(
                    job_description=job_description,
                    resume_json=json.dumps(inventory, indent=2),
                    section_summary=section_summary,
                ),
            }
        ],
    )
    log_usage("tailor_agent", CLAUDE_MODEL, response.usage)

    text = "\n".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    )
    return validate_tailoring(resume, _extract_json(text))
