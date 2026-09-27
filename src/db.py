import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from src.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    apply_url TEXT,
    posting_source TEXT,
    description TEXT,
    fit_score INTEGER,
    fit_reasoning TEXT,
    status TEXT NOT NULL DEFAULT 'discovered',
        -- discovered -> reviewing -> approved -> applied -> interview -> offer / rejected / withdrawn
    discovered_at TEXT NOT NULL,
    applied_at TEXT,
    tailored_resume_path TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS application_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    prompt TEXT NOT NULL,
    draft_answer TEXT,
    approved_answer TEXT,
    story_slugs_used TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    job_id INTEGER,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_job(job: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO jobs
            (company, title, location, apply_url, posting_source, description,
             fit_score, fit_reasoning, status, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'discovered', ?)""",
            (
                job["company"],
                job["title"],
                job.get("location"),
                job.get("apply_url"),
                job.get("posting_source"),
                job.get("description"),
                job.get("fit_score"),
                job.get("fit_reasoning"),
                now(),
            ),
        )
        return cur.lastrowid


def job_exists(company: str, title: str, apply_url: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE apply_url = ? OR (company = ? AND title = ?)",
            (apply_url, company, title),
        ).fetchone()
        return row is not None


def list_jobs(status: str = None) -> list:
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY fit_score DESC, discovered_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY fit_score DESC, discovered_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_job(job_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def update_job_status(job_id: int, status: str, **fields):
    fields["status"] = status
    if status == "applied":
        fields.setdefault("applied_at", now())
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [job_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)


def set_tailored_resume(job_id: int, path: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET tailored_resume_path = ? WHERE id = ?", (path, job_id)
        )


def add_question(job_id: int, prompt: str, draft_answer: str, story_slugs: list) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO application_questions
            (job_id, prompt, draft_answer, story_slugs_used, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (job_id, prompt, draft_answer, json.dumps(story_slugs), now()),
        )
        return cur.lastrowid


def approve_answer(question_id: int, approved_text: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE application_questions SET approved_answer = ? WHERE id = ?",
            (approved_text, question_id),
        )


def list_questions(job_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM application_questions WHERE job_id = ? ORDER BY id",
            (job_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def log_usage(agent: str, model: str, usage, job_id: int = None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO llm_usage_log (agent, job_id, model, input_tokens, output_tokens, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                agent,
                job_id,
                model,
                getattr(usage, "input_tokens", None),
                getattr(usage, "output_tokens", None),
                now(),
            ),
        )
