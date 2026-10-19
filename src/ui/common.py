from datetime import datetime, timezone

import streamlit as st

from src.config import ANTHROPIC_API_KEY, DATA_DIR, load_story_bank

STATUS_LABELS = {
    "discovered": "To review",
    "approved": "To apply",
    "applied": "Applied",
    "interview": "Interviewing",
    "offer": "Offer",
    "rejected": "Rejected",
    "skipped": "Skipped",
    "withdrawn": "Withdrawn",
}

# What you would most likely want to do next from each status.
NEXT_ACTIONS = {
    "discovered": [("Approve", "approved"), ("Skip", "skipped")],
    "approved": [("Mark as applied", "applied"), ("Skip", "skipped")],
    "applied": [("Got an interview", "interview"), ("Rejected", "rejected"), ("Withdraw", "withdrawn")],
    "interview": [("Got an offer", "offer"), ("Rejected", "rejected"), ("Withdraw", "withdrawn")],
    "offer": [("Withdraw", "withdrawn")],
    "rejected": [("Reopen as applied", "applied")],
    "skipped": [("Move back to review", "discovered")],
    "withdrawn": [("Reopen as applied", "applied")],
}


def rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:  # older Streamlit
        st.experimental_rerun()


def go_to_job(job_id):
    """Button callback: jump to the Pipeline page with this job open."""
    st.session_state["page"] = "Pipeline"
    st.session_state["selected_job"] = job_id


def go_to_page(page):
    st.session_state["page"] = page


def api_key_ready():
    return bool(ANTHROPIC_API_KEY)


def require_api_key():
    """Show an actionable error and return False when the key is missing."""
    if api_key_ready():
        return True
    st.error(
        "No Anthropic API key found. Add ANTHROPIC_API_KEY to the .env file in the "
        "project folder, then restart the app."
    )
    return False


def story_todo_count():
    """How many TODO placeholders are still in the story bank (None if no file)."""
    try:
        bank = load_story_bank()
    except FileNotFoundError:
        return None
    import json

    return json.dumps(bank).count("TODO")


def setup_checks():
    """Returns a list of (ok, message) for the sidebar status panel."""
    checks = []
    checks.append((api_key_ready(), "API key loaded" if api_key_ready() else "API key missing (add it to .env)"))
    for name in ("profile", "resume_bullets", "story_bank"):
        ok = (DATA_DIR / "{}.seed.json".format(name)).exists()
        checks.append((ok, "{}.seed.json found".format(name) if ok else "{}.seed.json missing".format(name)))
    todos = story_todo_count()
    if todos:
        checks.append((False, "Story bank has {} TODO placeholder(s) to fill in".format(todos)))
    return checks


def parse_ts(value):
    """Parse an ISO timestamp from the database into an aware datetime (or None)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def days_since(value):
    dt = parse_ts(value)
    if dt is None:
        return None
    return (datetime.now(timezone.utc) - dt).days
