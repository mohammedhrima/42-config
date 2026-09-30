"""Thin wrappers over the system: disk space, sizes, processes, git.

Each one exists so the code that uses it reads as a sentence, and so the failure
modes are visible instead of hidden behind a shell pipeline.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def free_mb(path: Path) -> int:
    """Free space, in MB, on the filesystem holding `path`.

    Walks up to the nearest existing parent, so it works for a path that is about
    to be created.
    """
    while not path.exists():
        if path.parent == path:
            return 0
        path = path.parent
    return shutil.disk_usage(path).free // (1024 * 1024)


def size_mb(path: Path) -> int:
    """Size of a directory tree, in MB. Zero when it does not exist."""
    if not path.exists():
        return 0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total // (1024 * 1024)


def can_read_write(path: Path) -> bool:
    """Whether this user can open `path` for reading and writing."""
    return os.access(path, os.R_OK | os.W_OK)


def is_running(process: str) -> bool:
    """Whether a process with exactly this name is running for this user."""
    result = subprocess.run(
        ["pgrep", "-u", str(Path.home().owner()), "-x", process],
        capture_output=True, check=False,
    )
    return result.returncode == 0


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command, capturing output. Never raises."""
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, check=False,
    )


def git(args: list[str], repo: Path | None = None) -> subprocess.CompletedProcess:
    """Run git, optionally inside `repo`."""
    command = ["git"]
    if repo is not None:
        command += ["-C", str(repo)]
    return run(command + args)


def git_succeeds(args: list[str], repo: Path | None = None) -> bool:
    """Whether a git command exits zero."""
    return git(args, repo).returncode == 0
