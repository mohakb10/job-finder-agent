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
