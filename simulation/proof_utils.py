"""Small shared helpers for reproducible simulation-run metadata."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def config_hash(config: dict[str, Any]) -> str:
    """Hash canonical JSON so equivalent configs have the same fingerprint."""
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hash(*paths: Path) -> str:
    """Hash source contents and repo-relative names into a portable fingerprint."""
    def display_name(path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return path.name

    digest = hashlib.sha256()
    for path in sorted(paths, key=display_name):
        digest.update(display_name(path).encode("utf-8"))
        digest.update(b"\\0")
        digest.update(path.read_bytes())
        digest.update(b"\\0")
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_worktree_dirty() -> bool | None:
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
