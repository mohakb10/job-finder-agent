# Data folder: public repo, private data

This mirrors the pattern from the project that inspired this one: the repo
is generic and public-safe by design, and your real personal data never
gets committed.

- `*.example.json` -- generic templates, safe to commit, checked into git.
- `*.seed.json` -- your real profile, resume, and story bank. Gitignored,
  never committed. This is what the app actually reads at runtime
  (`src/config.py` loads the `.seed.json` files).

## First-time setup

```bash
cp data/profile.example.json data/profile.seed.json
cp data/resume_bullets.example.json data/resume_bullets.seed.json
cp data/story_bank.example.json data/story_bank.seed.json
```

Then edit the three `*.seed.json` files with your real information. If you
forget this step, the app will raise a clear `FileNotFoundError` telling you
which file to create.

## If you edit your real data later

Just edit the `.seed.json` files directly -- they're never touched by git,
so there's nothing to sync or worry about conflicting with the repo.

## Updating your resume

`resume_bullets.seed.json` is the source of truth for every tailored PDF.
It has a list of `experience` entries and a list of `projects`, each with
its own bullets, and the code reads whatever is there. You can add or remove
a job or project, or change how many bullets it has, without touching any code.

For each bullet:

- `default` is the exact text from your resume.
- `variants` are other wordings you are happy to send. The tailoring agent
  may pick one of these instead of the default. Leave it as `[]` if you want
  that bullet to always read the same.
- `id` must be unique across the whole file.

After any edit, run:

```bash
python -m src.cli preview-resume
```

It renders your untailored resume to `output/resume_preview.pdf` (no API call)
and tells you if it runs past one page.
