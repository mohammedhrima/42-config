"""Managed directories.

A managed directory lives on goinfre and may be a clone of a repository, may be
symlinked into $HOME, and may need to survive the wipe that ends a session. Those
three properties describe every directory this configuration handles, so there is
one set of functions rather than one per special case.

goinfre is per workstation and is wiped when the session ends, so:

- ``link`` without ``keep`` is for caches. The symlink is removed at logout and
  the data goes with goinfre, because applications rebuild it.
- ``keep`` is for anything that cannot be rebuilt. It is moved back into $HOME,
  which follows the user between workstations.
- ``url`` means it can also be restored by cloning, so losing the copy is not
  fatal as long as the push succeeded.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import log
import system
from config import Config, Directory

#: Extra free space, in MB, required before moving a directory into $HOME.
HEADROOM_MB = 300


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _blocked(entry: Directory) -> bool:
    """Whether a guarded process is running, which makes moving unsafe."""
    if entry.guard and system.is_running(entry.guard):
        log.err(f"{entry.guard} is running. Close it, then try again")
        return True
    return False


def _clone(entry: Directory, target: Path) -> bool:
    """Clone the repository. Leaves nothing behind on failure."""
    log.info(f"cloning {entry.url}")
    if system.git_succeeds(["clone", entry.url, str(target)]):
        return True
    log.err(f"{entry.name}: clone failed")
    shutil.rmtree(target, ignore_errors=True)
    return False


def _build(entry: Directory, target: Path) -> bool:
    """Run the entry's build command in a freshly cloned directory."""
    if not entry.build:
        return True

    log.info(f"building: {entry.build}")
    result = system.run(["sh", "-c", entry.build], cwd=target)
    if result.returncode == 0:
        log.ok(f"{entry.name} built")
        return True

    log.err(f"{entry.name}: build failed")
    for line in result.stderr.strip().splitlines()[-3:]:
        log.info(line)
    return False


def _merge_existing(existing: Path, target: Path, prefer_local: list[str]) -> None:
    """Fold a real $HOME directory into the clone, then set it aside.

    Whatever the repository already carries wins, so data pushed from another
    workstation is not overwritten by a local stub. Files named in `prefer_local`
    are the exception: they belong to this machine, such as a login token.

    The original is renamed, never deleted.
    """
    log.info(f"merging existing {existing} into the clone")
    shutil.copytree(existing, target, dirs_exist_ok=True,
                    copy_function=_copy_if_absent)

    for name in prefer_local:
        source = existing / name
        if source.is_file():
            shutil.copy2(source, target / name)
            log.info(f"kept this machine's {name}")

    backup = existing.with_name(f"{existing.name}.bak.{_timestamp()}")
    existing.rename(backup)
    log.info(f"previous directory kept at {backup}")


def _copy_if_absent(source: str, destination: str) -> None:
    """copy2, but never overwrite an existing file."""
    if not Path(destination).exists():
        shutil.copy2(source, destination)


def realize(config: Config, entry: Directory, prefer_local: list[str] | None = None) -> bool:
    """Make one managed directory exist on goinfre and be linked from $HOME.

    Safe to run repeatedly: an already correct directory is only refreshed.
    """
    target = config.resolve(entry)
    link = config.resolve_link(entry)

    # A session that ended without logout leaves a symlink into a wiped goinfre.
    if link and link.is_symlink() and not link.exists():
        link.unlink()

    # Already correct. Refresh a repository, leave a plain directory alone.
    if link and link.is_symlink() and link.resolve() == target:
        if entry.is_repo:
            system.git(["pull", "--rebase", "--autostash"], target)
        return True

    if link and _blocked(entry):
        return False

    if not target.exists():
        # logout may have moved it into $HOME at the end of the last session.
        if link and link.is_dir() and not link.is_symlink() and entry.is_repo \
                and (link / ".git").is_dir():
            log.info(f"found {entry.name} in $HOME, moving it to goinfre")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(link), str(target))
        elif entry.is_repo:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not _clone(entry, target):
                return False
            if not _build(entry, target):
                # Leave nothing half-built: a directory that exists is treated as
                # done on the next run, so the build would never be retried.
                shutil.rmtree(target, ignore_errors=True)
                return False
        else:
            target.mkdir(parents=True, exist_ok=True)

    if link is None:
        return True

    # First run on a machine that already had a real directory here.
    if link.exists() and not link.is_symlink():
        _merge_existing(link, target, prefer_local or [])

    # After any copy, never before: copying carries the source's mode across.
    target.chmod(0o700)

    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    log.ok(f"{entry.link} -> {target}")

    if entry.is_repo:
        system.git(["pull", "--rebase", "--autostash"], target)
    return True


def carry_back(config: Config, entry: Directory) -> bool:
    """Move a directory into $HOME so it survives the goinfre wipe.

    Returns False when there is not enough room, which the caller must treat as
    "this data is still only on goinfre".
    """
    target = config.resolve(entry)
    link = config.resolve_link(entry)
    if link is None or not target.is_dir():
        return True

    needed = system.size_mb(target)
    available = system.free_mb(link.parent if link.parent.exists() else Path.home())

    if available < needed + HEADROOM_MB:
        log.err(f"{entry.link}: needs {needed}M, only {available}M free in $HOME")
        return False

    if link.is_symlink():
        link.unlink()
    log.info(f"moving {entry.link} back to $HOME ({needed}M into {available}M free)")
    link.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target), str(link))
    log.ok(f"{entry.link} kept in $HOME")
    return True


def drop(config: Config, entry: Directory) -> int:
    """Remove the symlink and delete the data. Returns the MB freed.

    Only for directories an application rebuilds by itself.
    """
    target = config.resolve(entry)
    link = config.resolve_link(entry)

    freed = system.size_mb(target)
    if link and link.is_symlink():
        link.unlink()
    shutil.rmtree(target, ignore_errors=True)

    if freed:
        log.ok(f"{entry.link or entry.path} dropped, {freed}M freed")
    return freed
