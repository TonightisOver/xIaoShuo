#!/usr/bin/env python3
"""Fail when repository text files contain provider-shaped API keys."""

from __future__ import annotations

import re
from pathlib import Path

KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")
IGNORED_DIRS = {".git", ".claude", "node_modules", "dist", ".venv", "logs"}
IGNORED_FILES = {".env"}
ALLOWED_VALUES = {
    "sk-1234567890abcdef1234567890abcdef",
}


def find_secret_candidates(root: Path) -> list[Path]:
    """Return text files containing non-placeholder provider-shaped keys."""
    matches: list[Path] = []
    for path in root.rglob("*"):
        if (
            not path.is_file()
            or path.name in IGNORED_FILES
            or path.suffix == ".log"
            or any(part in IGNORED_DIRS for part in path.parts)
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        candidates = KEY_PATTERN.findall(text)
        if any(candidate not in ALLOWED_VALUES for candidate in candidates):
            matches.append(path)
    return sorted(matches)


def main() -> int:
    matches = find_secret_candidates(Path.cwd())
    for path in matches:
        print(path)
    return 1 if matches else 0


if __name__ == "__main__":
    raise SystemExit(main())
