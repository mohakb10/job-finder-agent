import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_ANALYST_MODEL = os.environ.get("CLAUDE_ANALYST_MODEL", "claude-opus-4-8")
DB_PATH = ROOT / os.environ.get("DB_PATH", "data/pipeline.db")


def load_json(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        example_name = name.replace(".seed.json", ".example.json")
        raise FileNotFoundError(
            f"{path} not found. Copy data/{example_name} to data/{name} and fill in "
            f"your real information (see data/README.md)."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_profile() -> dict:
    return load_json("profile.seed.json")


def load_resume() -> dict:
    return load_json("resume_bullets.seed.json")


def load_story_bank() -> dict:
    return load_json("story_bank.seed.json")
