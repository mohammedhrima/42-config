"""Reclaiming the space Docker uses.

Docker's data root is on goinfre, so it is wiped when the workstation is. What
this adds is doing it deliberately at logout, and doing it through the daemon
first: `docker system prune` releases images, volumes and build cache properly,
and reports how much it freed.

A plain prune keeps anything still in use, which on a machine about to be wiped
is everything. So running containers are stopped first and the prune is told to
take unused images and volumes as well.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import log
import system

#: Long enough for containers to shut down, short enough not to hang a logout.
STOP_TIMEOUT = "10"


def is_available() -> bool:
    """Whether a docker CLI and a reachable daemon both exist."""
    if shutil.which("docker") is None:
        return False
    return system.run(["docker", "info", "--format", "{{.ServerVersion}}"]).returncode == 0


def data_root() -> Path | None:
    """Where the daemon keeps its data, as the daemon reports it."""
    result = system.run(["docker", "info", "--format", "{{.DockerRootDir}}"])
    if result.returncode != 0:
        return None
    root = result.stdout.strip()
    return Path(root) if root else None


def _running_containers() -> list[str]:
    result = system.run(["docker", "ps", "-q"])
    return [line for line in result.stdout.split() if line]


def clean() -> int:
    """Stop everything and prune. Returns MB still used afterwards."""
    if not is_available():
        log.info("docker is not running, nothing to clean")
        return 0

    root = data_root()
    before = system.size_mb(root) if root else 0
    log.step(f"Cleaning docker ({before}M)")

    running = _running_containers()
    if running:
        log.info(f"stopping {len(running)} running container(s)")
        system.run(["docker", "stop", "--time", STOP_TIMEOUT, *running])

    # -a takes images with no container left, --volumes takes named volumes.
    # Without both, a machine that is about to be wiped keeps everything.
    log.info("pruning containers, images, volumes and build cache")
    result = system.run(["docker", "system", "prune", "-a", "-f", "--volumes"])
    for line in result.stdout.strip().splitlines():
        if line.lower().startswith("total reclaimed"):
            log.ok(line.strip())

    after = system.size_mb(root) if root else 0
    if before and after < before:
        log.ok(f"docker went from {before}M to {after}M")
    return after
