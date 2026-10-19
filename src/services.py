"""
Thin service layer shared by the CLI and the Streamlit UI so both do exactly
the same thing when you search for jobs or tailor a resume.
"""
from src.agents.search_agent import search_jobs
from src.agents.tailor_agent import tailor_resume
from src.config import OUTPUT_DIR
from src.db import get_job, insert_job, job_exists, set_tailored_resume
from src.resume_pdf import render_resume_pdf

# Pipeline order, plus the statuses that mean "not going anywhere".
ACTIVE_STAGES = ["discovered", "approved", "applied", "interview", "offer"]
CLOSED_STATUSES = ["rejected", "skipped", "withdrawn"]
ALL_STATUSES = ACTIVE_STAGES + CLOSED_STATUSES
# Statuses that mean you actually submitted an application at some point.
SUBMITTED_STATUSES = ["applied", "interview", "offer", "rejected"]


def run_search(notes=None, max_searches=12):
    """Run the Search Agent and store anything new as 'discovered'.

    Returns (added, skipped_duplicates, malformed).
    """
    suggestions = search_jobs(extra_instructions=notes, max_searches=max_searches)
    added = skipped = malformed = 0
    for job in suggestions:
        if not job.get("company") or not job.get("title"):
            malformed += 1
            continue
        if job_exists(job["company"], job["title"], job.get("apply_url")):
            skipped += 1
            continue
        insert_job(job)
        added += 1
    return added, skipped, malformed


def tailor_for_job(job_id):
    """Generate a tailored resume PDF for a job.

    Returns (pdf_path, summary_of_emphasis).
    """
    job = get_job(job_id)
    if not job:
        raise ValueError("Job not found.")
    if not job.get("description"):
        raise ValueError("This job has no description yet. Paste the posting text first.")

    tailored = tailor_resume(job["description"])
    safe_company = "".join(c for c in job["company"] if c.isalnum())[:30]
    out_path = OUTPUT_DIR / "resume_{}_{}.pdf".format(job_id, safe_company)
    render_resume_pdf(tailored, str(out_path))
    set_tailored_resume(job_id, str(out_path))
    return str(out_path), tailored.get("summary_of_emphasis", "")
