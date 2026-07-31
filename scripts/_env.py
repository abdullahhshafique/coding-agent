"""Minimal .env loader for one-off evaluation/curation scripts.

The production tools read GITHUB_TOKEN / GROQ_API_KEY from process env vars
only (never from a committed config file — PRD section 7). These scripts load
the local .env the same way so a manual `python run_evaluation.py` works
without exporting vars first. Keys are never printed.
"""

from __future__ import annotations

import os


def load_env(path: str = ".env") -> None:
    """Populate os.environ from a KEY=VALUE .env file, without overriding
    variables that are already set in the real environment."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
