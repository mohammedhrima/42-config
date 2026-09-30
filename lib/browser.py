"""Backing up the Chrome profile to a private repository.

The profile lives in $HOME so it already survives changing workstation. This is
the off-machine copy, for when $HOME itself is lost.

Only files that carry state are copied. Caches, extensions, IndexedDB and service
workers are left out: they are large and Chrome rebuilds them.

Each push replaces the history with a single commit. Without that, `History` is a
40M+ binary database that git cannot diff, so every backup would add its whole
size again and the repository would pass a gigabyte within weeks.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import log
import system

CHROME_DIR = Path.home() / ".config" / "google-chrome"

#: Copied from each profile directory.
PROFILE_FILES = (
    "Bookmarks", "Bookmarks.bak",
    "Preferences", "Secure Preferences",
    "History", "Favicons", "Top Sites", "Shortcuts",
    "Web Data", "Login Data", "Cookies",
    "Custom Dictionary.txt",
)

#: Copied from the top level. `Local State` lists the profiles, so without it a
#: restore would not know that "Profile 3" exists.
ROOT_FILES = ("Local State", "First Run")


def _profiles(directory: Path) -> list[Path]:
    """Profile directories, in a stable order."""
    if not directory.is_dir():
        return []
    found = [p for p in directory.iterdir()
             if p.is_dir() and (p.name == "Default" or p.name.startswith("Profile"))]
    return sorted(found, key=lambda p: p.name)


def _chrome_is_running() -> bool:
    """Chrome keeps these files open as live SQLite databases.

    Copying one mid-write produces a backup that cannot be opened.
    """
    if system.is_running("chrome"):
        log.err("Chrome is running. Close it, then try again")
        return True
    return False


def _copy_listed(source: Path, destination: Path, names: tuple[str, ...]) -> None:
    """Copy whichever of `names` exist. A profile need not have all of them."""
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        candidate = source / name
        if candidate.is_file():
            shutil.copy2(candidate, destination / name)


def save(repo_url: str, work_dir: Path) -> bool:
    """Copy the profile into a fresh clone, commit once, and force-push."""
    if not repo_url:
        return True
    if not CHROME_DIR.is_dir():
        log.info(f"no Chrome profile at {CHROME_DIR}")
        return True
    if _chrome_is_running():
        return False

    log.step(f"Backing up the Chrome profile to {repo_url}")

    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True)
    system.git(["init", "-q"], work_dir)
    system.git(["remote", "add", "origin", repo_url], work_dir)

    _copy_listed(CHROME_DIR, work_dir, ROOT_FILES)

    profiles = _profiles(CHROME_DIR)
    if not profiles:
        log.err("found no profiles to back up")
        return False

    for profile in profiles:
        _copy_listed(profile, work_dir / profile.name, PROFILE_FILES)
        log.ok(f"{profile.name}  {system.size_mb(work_dir / profile.name)}M")

    total = system.size_mb(work_dir)
    log.info(f"{len(profiles)} profile(s), {total}M total")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    host = system.run(["hostname", "-s"]).stdout.strip()

    system.git(["add", "-A"], work_dir)
    if not system.git_succeeds(["commit", "-q", "-m", f"chrome profile: {stamp} ({host})"], work_dir):
        log.err("commit failed")
        return False
    system.git(["branch", "-M", "main"], work_dir)

    log.info(f"pushing {total}M...")
    result = system.git(["push", "-f", "-u", "origin", "main"], work_dir)
    if result.returncode != 0:
        log.err(f"push failed: {result.stderr.strip().splitlines()[-1:] or ['unknown']}")
        return False

    log.ok("pushed")
    return True


def load(repo_url: str, work_dir: Path) -> bool:
    """Restore the backed-up files onto this machine."""
    if not repo_url:
        log.info("no backup repository configured")
        return True
    if _chrome_is_running():
        return False

    log.step(f"Restoring the Chrome profile from {repo_url}")
    shutil.rmtree(work_dir, ignore_errors=True)
    if not system.git_succeeds(["clone", "--depth", "1", "-q", repo_url, str(work_dir)]):
        log.err("clone failed")
        return False

    CHROME_DIR.mkdir(parents=True, exist_ok=True)
    _copy_listed(work_dir, CHROME_DIR, ROOT_FILES)

    for profile in _profiles(work_dir):
        _copy_listed(profile, CHROME_DIR / profile.name, PROFILE_FILES)
        log.ok(f"{profile.name} restored")

    log.info("saved passwords and cookies are encrypted against this machine's")
    log.info("keyring, so Chrome may ask you to sign in again")
    return True


def show(repo_url: str, work_dir: Path) -> bool:
    """Print what the backup currently holds."""
    if not repo_url:
        log.info("no backup repository configured")
        return True

    log.step("Backup contents")
    shutil.rmtree(work_dir, ignore_errors=True)
    if not system.git_succeeds(["clone", "--depth", "1", "-q", repo_url, str(work_dir)]):
        log.err("clone failed")
        return False

    for profile in _profiles(work_dir):
        has_bookmarks = "yes" if (profile / "Bookmarks").is_file() else "NO"
        log.info(f"{profile.name:<12} {system.size_mb(profile)}M  bookmarks:{has_bookmarks}")
    return True
