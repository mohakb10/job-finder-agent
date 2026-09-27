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
  -> offer / rejected / withdrawn`.

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
python -m src.cli reject 4          # not a fit, get it out of the queue

# 4. Generate a tailored resume for an approved job
python -m src.cli tailor 3          # writes output/resume_3_CompanyName.pdf

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
- **No web app / auth / hosted DB.** It's a single-user CLI against a local
  SQLite file. If this becomes something you want a UI for later, a
  Streamlit page over the same `db.py` functions would be a small addition
  (see `ROADMAP.md` below for the natural extension points, if you add
  one).
- **Bounded resume tailoring.** The tailoring agent choosing from a fixed
  bullet + pre-approved-synonym inventory (rather than freeform rewriting)
  means you can trust every generated resume is factually identical to
  your source resume -- it just emphasizes different parts of the truth
  for different roles.

## Extending it

Natural next additions, roughly in order of value if you keep using this:
1. A `dedupe`/refresh command that re-scores `discovered` jobs if you tweak
   `profile.json` criteria mid-search.
2. A cost dashboard reading `llm_usage_log` (already logged on every call).
3. A `local/` folder pattern like the original project if you ever want to
   version-control this without committing your real resume/story data.
