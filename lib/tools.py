"""Downloading development tools into /goinfre/$USER/tools.

Every tool is a download plus one of four ways of unpacking it, so each unpacking
method is written once and each tool only says which one it uses and where to get
it. Nothing here needs root.

goinfre is wiped when a session ends, so these are re-downloaded on a new
workstation. That is the trade for keeping a 4.7G $HOME usable.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import log
import system


@dataclass(frozen=True)
class Tool:
    """One installable tool."""

    name: str
    #: Returns the download URL. A function because most need a lookup first.
    url: Callable[[], str]
    #: Unpacks the downloaded file into the install directory.
    unpack: Callable[[Path, Path], None]
    #: Directory added to PATH, relative to the install directory.
    bin_subdir: str = ""

    def bin_path(self, tools_dir: Path) -> Path:
        directory = tools_dir / self.name
        return directory / self.bin_subdir if self.bin_subdir else directory


# --------------------------------------------------------------------------
# Unpacking
# --------------------------------------------------------------------------

def unpack_tarball(archive: Path, target: Path) -> None:
    """Extract a tarball whose contents sit inside one top-level directory."""
    with tarfile.open(archive) as tar:
        roots = {name.split("/")[0] for name in tar.getnames()}
        if len(roots) != 1:
            raise ValueError(f"expected one top-level directory, found {sorted(roots)}")
        root = roots.pop()
        tar.extractall(target.parent, filter="data")

    shutil.rmtree(target, ignore_errors=True)
    (target.parent / root).rename(target)


def unpack_zip(archive: Path, target: Path) -> None:
    """Extract a zip that holds loose files, such as a single binary."""
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as archive_file:
        archive_file.extractall(target)
    for entry in target.iterdir():
        if entry.is_file():
            entry.chmod(0o755)


def unpack_android(archive: Path, target: Path) -> None:
    """Extract Android's cmdline-tools, which sdkmanager expects at a fixed path.

    The zip contains ``cmdline-tools/``, but the tool only works when that sits at
    ``cmdline-tools/latest/``, so it is moved there.
    """
    staging = target.parent / f".{target.name}-staging"
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(archive) as archive_file:
        archive_file.extractall(staging)

    destination = target / "cmdline-tools" / "latest"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(destination, ignore_errors=True)
    (staging / "cmdline-tools").rename(destination)
    shutil.rmtree(staging, ignore_errors=True)

    for script in (destination / "bin").iterdir():
        script.chmod(0o755)


def unpack_appimage(archive: Path, target: Path) -> None:
    """Extract an AppImage instead of running it.

    Running one needs FUSE, which needs root, and ``--appimage-extract-and-run``
    unpacks the whole thing to /tmp on every launch.
    """
    staging = target.parent / f".{target.name}-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    binary = staging / "app.AppImage"
    shutil.move(str(archive), str(binary))
    binary.chmod(0o755)

    subprocess.run([str(binary), "--appimage-extract"], cwd=staging,
                   stdout=subprocess.DEVNULL, check=True)
    shutil.rmtree(target, ignore_errors=True)
    (staging / "squashfs-root").rename(target)
    shutil.rmtree(staging, ignore_errors=True)


# --------------------------------------------------------------------------
# Where each tool comes from
# --------------------------------------------------------------------------

def _latest_node() -> str:
    page = system.run(["curl", "-fsSL", "https://nodejs.org/dist/latest/"]).stdout
    match = re.search(r"node-v[\d.]+-linux-x64\.tar\.xz", page)
    if not match:
        raise LookupError("could not find the current Node version")
    return f"https://nodejs.org/dist/latest/{match.group()}"


def _latest_flutter() -> str:
    base = "https://storage.googleapis.com/flutter_infra_release/releases"
    manifest = system.run(["curl", "-fsSL", f"{base}/releases_linux.json"]).stdout
    match = re.search(r"stable/linux/flutter_linux_[\d.]+-stable\.tar\.xz", manifest)
    if not match:
        raise LookupError("could not find the current stable Flutter")
    return f"{base}/{match.group()}"


def _latest_beekeeper() -> str:
    """Read the version from the redirect, not the GitHub API.

    The whole campus shares one public IP and the API allows 60 unauthenticated
    calls an hour per IP, so it runs out.
    """
    redirect = system.run([
        "curl", "-fsIL", "-o", "/dev/null", "-w", "%{url_effective}",
        "https://github.com/beekeeper-studio/beekeeper-studio/releases/latest",
    ]).stdout
    match = re.search(r"/tag/v(.+)$", redirect.strip())
    if not match:
        raise LookupError("could not find the current Beekeeper version")
    version = match.group(1)
    return ("https://github.com/beekeeper-studio/beekeeper-studio/releases/download/"
            f"v{version}/Beekeeper-Studio-{version}.AppImage")


TOOLS: dict[str, Tool] = {
    "code": Tool(
        name="code",
        url=lambda: "https://update.code.visualstudio.com/latest/linux-x64/stable",
        unpack=unpack_tarball,
        bin_subdir="bin",
    ),
    "node": Tool(name="node", url=_latest_node, unpack=unpack_tarball, bin_subdir="bin"),
    "uv": Tool(
        name="uv",
        url=lambda: ("https://github.com/astral-sh/uv/releases/latest/download/"
                     "uv-x86_64-unknown-linux-gnu.tar.gz"),
        unpack=unpack_tarball,
    ),
    "flutter": Tool(name="flutter", url=_latest_flutter, unpack=unpack_tarball,
                    bin_subdir="bin"),
    "ninja": Tool(
        name="ninja",
        url=lambda: ("https://github.com/ninja-build/ninja/releases/latest/download/"
                     "ninja-linux.zip"),
        unpack=unpack_zip,
    ),
    "android": Tool(
        name="android",
        url=lambda: ("https://dl.google.com/android/repository/"
                     "commandlinetools-linux-9862592_latest.zip"),
        unpack=unpack_android,
        bin_subdir="cmdline-tools/latest/bin",
    ),
    "beekeeper": Tool(name="beekeeper", url=_latest_beekeeper, unpack=unpack_appimage),
}


def _download(url: str, destination: Path) -> bool:
    """Fetch a URL, showing a progress bar. Leaves nothing behind on failure."""
    log.info(f"from {url}")
    log.info("downloading...")
    result = subprocess.run(["curl", "-fL", "--progress-bar", url, "-o", str(destination)],
                            check=False)
    if result.returncode == 0:
        return True
    destination.unlink(missing_ok=True)
    return False


def install(tool: Tool, tools_dir: Path) -> bool:
    """Install one tool. Already-installed tools are left alone."""
    target = tools_dir / tool.name
    if target.is_dir():
        log.info(f"{tool.name} already installed")
        return True

    log.step(f"Installing {tool.name}")
    tools_dir.mkdir(parents=True, exist_ok=True)
    archive = tools_dir / f".{tool.name}-download"

    try:
        url = tool.url()
    except LookupError as error:
        log.err(f"{tool.name}: {error}")
        return False

    if not _download(url, archive):
        log.err(f"{tool.name}: download failed")
        return False

    log.info(f"unpacking into {target}")
    try:
        tool.unpack(archive, target)
    except Exception as error:                      # noqa: BLE001 - report and clean up
        log.err(f"{tool.name}: unpacking failed: {error}")
        shutil.rmtree(target, ignore_errors=True)
        return False
    finally:
        archive.unlink(missing_ok=True)

    log.ok(f"{tool.name} ready, {system.size_mb(target)}M in {target}")
    return True
