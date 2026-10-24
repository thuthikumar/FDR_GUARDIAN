"""Environment-backed configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Load the project-level .env for local development; existing process variables win.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def database_url() -> str | None:
    """Return the database URL, if configured."""
    value = os.getenv("DATABASE_URL", "").strip()
    return value or None
