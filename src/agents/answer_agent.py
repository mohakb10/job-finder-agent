"""
Answer Generation Agent
-----------------------
For a given application short-answer prompt, retrieves relevant stories from
the story bank via simple keyword overlap (deterministic, not model-driven),
then makes one grounded Claude completion that drafts an answer using ONLY
those stories as source material. You review/edit before submitting -- this
never submits anything.
"""
import re

import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, load_story_bank
from src.db import log_usage

SYSTEM_PROMPT = """You are drafting a short answer to a job application question
on behalf of a candidate. You must ONLY use the factual content in the
stories provided below -- do not invent any details, numbers, companies, or
outcomes not present in these stories. If the stories don't fully answer the
question, write an honest, appropriately general answer and note in your
final line "[NOTE: story bank doesn't fully cover this -- edit before
submitting]" rather than fabricating specifics.

Keep the answer concise (roughly 100-180 words unless the question implies
otherwise), in first person, and in a natural, non-corporate voice.

Relevant stories (JSON):
{stories}

Application question:
{prompt}

Respond with ONLY the answer text -- no preamble, no markdown headers.
"""

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "you", "your", "did", "was", "were", "how", "what", "why", "tell", "me",
    "about", "time", "describe", "when", "that", "this", "have", "has",
}


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-z']+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def retrieve_stories(prompt: str, top_k: int = 3) -> list:
    """
    Deterministic keyword-overlap retrieval against story title +
    competencies + good_for_questions. No LLM call here -- retrieval is
    reproducible and auditable.
    """
    bank = load_story_bank()["stories"]
    prompt_tokens = _tokenize(prompt)

    scored = []
    for story in bank:
        haystack = " ".join(
            [story["title"]]
            + story["competencies"]
            + story["good_for_questions"]
        )
        story_tokens = _tokenize(haystack)
        overlap = len(prompt_tokens & story_tokens)
        if overlap > 0:
            scored.append((overlap, story))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:top_k]] if scored else bank[:top_k]


def draft_answer(prompt: str) -> dict:
    """
    Returns {"draft": str, "story_slugs_used": [str, ...]}
    """
    stories = retrieve_stories(prompt)
    slugs = [s["slug"] for s in stories]

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    import json as _json

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": SYSTEM_PROMPT.format(
                    stories=_json.dumps(stories, indent=2), prompt=prompt
                ),
            }
        ],
    )
    log_usage("answer_agent", CLAUDE_MODEL, response.usage)

    draft = "\n".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ).strip()
    return {"draft": draft, "story_slugs_used": slugs}
