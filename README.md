# Job Finder Agent (Mohak's version)

A personal, local-first job-application command center, tuned for a Data
Scientist II targeting Senior DS / Applied Scientist / MLE roles. No
deployment, no auth, no database server -- just a CLI, a SQLite file, and
the Claude API.

**This never auto-applies anywhere.** It finds postings, drafts a tailored
resume PDF, and drafts grounded answers to short-answer questions. You
review everything and submit applications yourself.

## What's here

- **Job Search Agent** (`src/agents/search_agent.py`) -- Claude + web search
  finds currently-open postings and scores them against your target profile
  in `data/profile.json`. Suggestions land as `discovered` in the pipeline;
  nothing is auto-approved.
- **Resume Tailoring Agent** (`src/agents/tailor_agent.py`) -- given a job
  description, picks bullet order + one of a few pre-approved phrasing
  variants per bullet. It can never invent a bullet or edit a number --
  every choice it returns is re-validated in code against
  `data/resume_bullets.json` before rendering.
- **PDF renderer** (`src/resume_pdf.py`) -- renders the tailored selection
  into a clean, ATS-friendly single-column PDF via reportlab.
- **Answer Generation Agent** (`src/agents/answer_agent.py`) -- for a given
  application question, deterministically retrieves the most relevant
  stories from `data/story_bank.json` (keyword overlap, no LLM involved in
  retrieval), then makes one grounded Claude call to draft an answer using
  only those stories.
- **Pipeline Analyst** (`src/agents/analyst_agent.py`) -- an occasional
  Claude Opus pass over your whole application history, triggered by a new
  interview or 10+ new applications (or run with `--force`). Never edits
  anything, just writes you a report.
- **Pipeline** -- a SQLite table (`data/pipeline.db`, created on first run)
  tracking each job through `discovered -> approved -> applied -> interview
  -> offer`, or out of the pipeline as `rejected`, `skipped` or `withdrawn`.

## Setup

```bash
cd job-finder-agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY

cp data/profile.example.json data/profile.seed.json
cp data/resume_bullets.example.json data/resume_bullets.seed.json
cp data/story_bank.example.json data/story_bank.seed.json
```

The `*.seed.json` files are gitignored and hold your real profile, resume,
and story bank -- see `data/README.md`. The `*.example.json` files are
generic templates safe to commit; the app reads the `.seed.json` files at
runtime and will tell you exactly what to copy if you forget this step.

Before running anything, edit **`data/story_bank.seed.json`** and fill in
the `TODO` markers (or, if you're starting fresh from the example, write
your own stories in) with real specifics (exact technical decisions, team
context, "why I'm looking"). The story bank is what makes drafted answers
sound like you instead of a generic paraphrase of your resume bullets --
skipping this step is the single biggest quality lever in this whole
system.

Also sanity-check **`data/profile.seed.json`** -- especially `target.titles`,
`domains_avoid`, and `search_queries_seed` -- since that's what the search
agent optimizes for.

## The web UI

```bash
source venv/bin/activate
streamlit run app.py
```

This opens a page in your browser (usually http://localhost:8501). It reads and
writes the same `data/pipeline.db` as the CLI, so you can mix the two freely.

- **Dashboard**: your whole search as one strip (to review, to apply, applied,
  interviewing, offer), plus what is waiting for review, what needs a follow-up
  after 14 days, applications per week, and the spread of fit scores.
- **Pipeline**: filterable table of every job. Open one to change its status,
  paste the full posting text, keep notes, generate and preview the tailored
  resume PDF, and draft answers to application questions. You can also add a
  job you found yourself.
- **Search**: run the search agent and approve or skip what it finds.
- **Analyst**: run the pipeline analysis and keep the latest report.

Search results only include a short summary of each role. Before tailoring a
resume, paste the full posting into the job's Overview tab, since tailoring can
only emphasize what the text says.

## Day-to-day usage

```bash
# 1. Find new postings
python -m src.cli search
python -m src.cli search --notes "focus on Series C+ security startups this time"

# 2. Review what it found
python -m src.cli list --status discovered
python -m src.cli show 3

# 3. Approve the ones worth applying to
python -m src.cli promote 3
python -m src.cli reject 4          # not a fit, marks it skipped

# 4. Generate a tailored resume for an approved job
python -m src.cli tailor 3          # writes output/resume_3_CompanyName.pdf
python -m src.cli preview-resume     # render your untailored resume (no API call), after editing it

# 5. Draft answers to any short-answer questions on the application
python -m src.cli ask 3 "Why are you interested in this role?"
python -m src.cli questions 3       # review drafts
python -m src.cli approve-answer 7 "your final edited text"

# 6. After you apply (yourself, on the company site)
python -m src.cli applied 3

# 7. As things progress
python -m src.cli status 3 interview
python -m src.cli status 3 rejected

# 8. Every so often, see what's actually working
python -m src.cli analyze
```

Run `python -m src.cli --help` any time for the full command list.

## Design notes / things kept deliberately simple

- **No browser automation.** Original inspiration (a friend's project) had a
  "computer apply run" handoff to Playwright. Cut here on purpose --
  auto-filling real forms while actively job hunting is a good way to
  break an application you cared about. Tailoring + drafting is the
  leverage; submitting is 30 seconds of your own attention.
- **Local only, no auth or hosted DB.** The CLI and the Streamlit UI are two
  front ends on the same local SQLite file (`src/db.py`) and the same service
  layer (`src/services.py`), so there is one place where behavior lives.
- **Bounded resume tailoring.** The tailoring agent choosing from a fixed
  bullet + pre-approved-synonym inventory (rather than freeform rewriting)
  means you can trust every generated resume is factually identical to
  your source resume -- it just emphasizes different parts of the truth
  for different roles.

## Extending it

Natural next additions, roughly in order of value if you keep using this:
1. A `dedupe`/refresh command that re-scores `discovered` jobs if you tweak
   `profile.json` criteria mid-search.
2. A per-run cost breakdown from `llm_usage_log` (the dashboard already shows totals).
3. A `local/` folder pattern like the original project if you ever want to
   version-control this without committing your real resume/story data.
