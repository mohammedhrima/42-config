"""VS Code extension management.

The wanted extensions are listed in ~/42.toml. These functions take that set and
return the updated one; writing it back is the caller's job, so this module never
touches the config file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import log


def _installed(code: Path) -> set[str]:
    """Extension ids VS Code currently has, lowercased.

    The marketplace is inconsistent about capitalisation (`Dart-Code.flutter`
    versus `dart-code.flutter`), so every comparison is done in lower case.
    """
    result = subprocess.run(
        [str(code), "--list-extensions"],
        capture_output=True, text=True, check=False,
    )
    return {line.strip().lower() for line in result.stdout.splitlines() if line.strip()}


def _install_one(code: Path, ident: str) -> bool:
    """Install a single extension. Returns True on success."""
    result = subprocess.run(
        [str(code), "--install-extension", ident, "--force"],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


def sync(code: Path, wanted: dict[str, str]) -> int:
    """Install everything listed that is not installed yet."""
    if not wanted:
        log.info("no extensions listed in ~/42.toml")
        return 0

    log.step("Installing VS Code extensions")
    have = _installed(code)
    failed = 0

    for ident in wanted.values():
        if ident.lower() in have:
            log.info(f"{ident} already installed")
        elif _install_one(code, ident):
            log.ok(ident)
        else:
            log.err(f"{ident} failed to install")
            failed += 1

    return 1 if failed else 0


def add(code: Path, wanted: dict[str, str], ident: str,
        name: str | None = None) -> tuple[int, dict[str, str]]:
    """Install one extension and return the updated wanted set."""
    updated = dict(wanted)
    name = name or ident.rsplit(".", 1)[-1]

    if any(existing.lower() == ident.lower() for existing in updated.values()):
        log.info(f"{ident} already listed")
    else:
        updated[name] = ident
        log.ok(f"added {ident}")

    log.step(f"Installing {ident}")
    if _install_one(code, ident):
        log.ok(ident)
        return 0, updated
    log.err(f"{ident} failed to install")
    return 1, updated


def remove(wanted: dict[str, str], ident: str) -> tuple[int, dict[str, str]]:
    """Drop one extension from the set. Does not uninstall it."""
    updated = {n: i for n, i in wanted.items() if i.lower() != ident.lower()}
    if len(updated) == len(wanted):
        log.info(f"{ident} was not listed")
        return 0, updated

    log.ok(f"{ident} removed from the list")
    log.info(f"still installed. To remove it: code --uninstall-extension {ident}")
    return 0, updated


def snapshot(code: Path) -> tuple[int, dict[str, str]]:
    """Return the currently installed extensions as a wanted set."""
    log.step("Reading installed extensions")
    result = subprocess.run([str(code), "--list-extensions"],
                            capture_output=True, text=True, check=False)
    ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not ids:
        log.err("VS Code reported no extensions, refusing to save an empty list")
        return 1, {}

    for ident in ids:
        log.info(ident)
    log.ok(f"{len(ids)} extensions")
    return 0, {ident.rsplit(".", 1)[-1]: ident for ident in ids}


def show(code: Path, wanted: dict[str, str]) -> int:
    """Print which listed extensions are installed."""
    if not wanted:
        log.info("no extensions listed in ~/42.toml")
        return 0

    log.step("Extensions listed in ~/42.toml")
    have = _installed(code)
    for ident in wanted.values():
        if ident.lower() in have:
            log.ok(ident)
        else:
            log.info(f"{ident}  NOT INSTALLED")
    return 0
