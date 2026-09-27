import click
from tabulate import tabulate

from src.agents.analyst_agent import is_eligible_for_analysis, run_analysis
from src.agents.answer_agent import draft_answer
from src.agents.search_agent import search_jobs
from src.agents.tailor_agent import tailor_resume
from src.config import OUTPUT_DIR
from src.db import (
    add_question,
    approve_answer,
    get_job,
    init_db,
    insert_job,
    job_exists,
    list_jobs,
    list_questions,
    set_tailored_resume,
    update_job_status,
)
from src.resume_pdf import render_resume_pdf


@click.group()
def cli():
    """Personal job-finder agent CLI."""
    init_db()


@cli.command()
def setup():
    """Initialize the local database (safe to re-run)."""
    init_db()
    click.echo(f"Database ready.")


@cli.command()
@click.option("--notes", default=None, help="Extra instructions for this search run, e.g. 'focus on Series B-D startups'")
def search(notes):
    """Run the Job Search Agent and add new suggestions to the pipeline as 'discovered'."""
    click.echo("Searching for openings... (this makes several web searches, may take a minute)")
    suggestions = search_jobs(extra_instructions=notes)

    added, skipped = 0, 0
    for job in suggestions:
        if job_exists(job["company"], job["title"], job.get("apply_url")):
            skipped += 1
            continue
        insert_job(job)
        added += 1

    click.echo(f"Added {added} new suggestion(s), skipped {skipped} already in pipeline.")
    click.echo("Run 'python -m src.cli list --status discovered' to review them.")


@cli.command(name="list")
@click.option("--status", default=None, help="Filter by status (discovered, reviewing, approved, applied, interview, offer, rejected, withdrawn)")
def list_cmd(status):
    """List jobs in the pipeline."""
    jobs = list_jobs(status=status)
    if not jobs:
        click.echo("No jobs found.")
        return
    rows = [
        [j["id"], j["company"], j["title"][:40], j["fit_score"], j["status"], j.get("location") or ""]
        for j in jobs
    ]
    click.echo(tabulate(rows, headers=["ID", "Company", "Title", "Fit", "Status", "Location"]))


@cli.command()
@click.argument("job_id", type=int)
def show(job_id):
    """Show full details for one job."""
    job = get_job(job_id)
    if not job:
        click.echo("Job not found.")
        return
    for k, v in job.items():
        click.echo(f"{k}: {v}")


@cli.command()
@click.argument("job_id", type=int)
def promote(job_id):
    """Mark a discovered job as approved -- ready to tailor a resume for."""
    job = get_job(job_id)
    if not job:
        click.echo("Job not found.")
        return
    update_job_status(job_id, "approved")
    click.echo(f"Job {job_id} ({job['company']} - {job['title']}) approved.")


@cli.command()
@click.argument("job_id", type=int)
def reject(job_id):
    """Mark a job as rejected/not a fit -- removes it from your active review queue."""
    update_job_status(job_id, "withdrawn")
    click.echo(f"Job {job_id} marked withdrawn.")


@cli.command()
@click.argument("job_id", type=int)
def tailor(job_id):
    """Generate a tailored resume PDF for an approved job."""
    job = get_job(job_id)
    if not job:
        click.echo("Job not found.")
        return
    if not job.get("description"):
        click.echo("This job has no description saved -- add one with a DB edit or re-run search with better notes.")
        return

    click.echo("Tailoring resume...")
    tailored = tailor_resume(job["description"])
    click.echo(f"Emphasis: {tailored['summary_of_emphasis']}")

    safe_company = "".join(c for c in job["company"] if c.isalnum())[:30]
    out_path = OUTPUT_DIR / f"resume_{job_id}_{safe_company}.pdf"
    render_resume_pdf(tailored, str(out_path))
    set_tailored_resume(job_id, str(out_path))
    click.echo(f"Saved: {out_path}")
    click.echo("Review it before attaching to any real application.")


@cli.command()
@click.argument("job_id", type=int)
@click.argument("prompt")
def ask(job_id, prompt):
    """Draft an answer to an application short-answer question, grounded in your story bank."""
    job = get_job(job_id)
    if not job:
        click.echo("Job not found.")
        return
    result = draft_answer(prompt)
    qid = add_question(job_id, prompt, result["draft"], result["story_slugs_used"])
    click.echo(f"\n--- Draft answer (question id {qid}) ---")
    click.echo(result["draft"])
    click.echo(f"\nGrounded in stories: {', '.join(result['story_slugs_used'])}")
    click.echo("Edit as needed, then run 'approve-answer' to lock in the final text.")


@cli.command(name="approve-answer")
@click.argument("question_id", type=int)
@click.argument("final_text")
def approve_answer_cmd(question_id, final_text):
    """Save your final, edited version of a drafted answer."""
    approve_answer(question_id, final_text)
    click.echo("Saved.")


@cli.command(name="questions")
@click.argument("job_id", type=int)
def questions_cmd(job_id):
    """List drafted/approved questions for a job."""
    qs = list_questions(job_id)
    if not qs:
        click.echo("No questions drafted yet for this job.")
        return
    for q in qs:
        click.echo(f"\n[{q['id']}] {q['prompt']}")
        click.echo(f"  Draft:    {q['draft_answer']}")
        click.echo(f"  Approved: {q['approved_answer'] or '(not yet approved)'}")


@cli.command()
@click.argument("job_id", type=int)
def applied(job_id):
    """Mark a job as applied (after you've submitted it yourself)."""
    update_job_status(job_id, "applied")
    click.echo(f"Job {job_id} marked applied.")


@cli.command()
@click.argument("job_id", type=int)
@click.argument("new_status", type=click.Choice(["interview", "offer", "rejected", "withdrawn"]))
def status(job_id, new_status):
    """Update a job's status as things progress (interview, offer, rejected, withdrawn)."""
    update_job_status(job_id, new_status)
    click.echo(f"Job {job_id} marked {new_status}.")


@cli.command()
@click.option("--force", is_flag=True, help="Run even if the usual trigger conditions aren't met")
def analyze(force):
    """Run the Pipeline Analyst (Opus) over your full application history."""
    if not force and not is_eligible_for_analysis():
        click.echo(
            "Not enough new signal yet (need 1+ interview or 10+ applications). "
            "Use --force to run anyway."
        )
        return
    click.echo("Running pipeline analysis (this uses Opus, costs more than other commands)...")
    report = run_analysis()
    click.echo("\n" + report)


if __name__ == "__main__":
    cli()
