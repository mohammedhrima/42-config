"""Reading ~/42.toml.

Everything personal lives in that one file. This repository contains no names,
URLs or machine details, so it can be shared as it is: a student edits only their
own ~/42.toml.

A missing file is not an error. Every setting defaults to doing nothing, so an
untouched install behaves like a plain shell.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = Path.home() / "42.toml"

STARTER_CONFIG = """# Personal settings for 42-config.

[git]
name = ""
email = ""

[display]
resolution = ""
output = ""
gnome_tweaks = false

[tools]
# These tools are installed by 42 space on each workstation.
enabled = ["code", "node", "uv"]

[android]
api_level = 36

[browser]
backup_repo = ""

[extensions]

[vscode.settings]
"workbench.colorTheme" = "Default Dark Modern"
"""


def ensure_file(path: Path = CONFIG_FILE) -> None:
    """Create the starter config once, without overwriting a file made meanwhile."""
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(STARTER_CONFIG)
    except FileExistsError:
        pass


@dataclass(frozen=True)
class Directory:
    """A directory managed on goinfre.

    One concept covers every case:

    - a cache moved out of ``$HOME``: ``path`` and ``link``
    - a repository cloned for work: ``path`` and ``url``
    - a repository symlinked into ``$HOME``: ``path``, ``url`` and ``link``
    """

    #: Where it lives, relative to /goinfre/$USER.
    path: str
    #: Repository to clone. Empty means create an empty directory instead.
    url: str = ""
    #: Path relative to $HOME to symlink to it. Empty means no symlink.
    link: str = ""
    #: Whether logout moves it back into $HOME instead of letting it be wiped.
    keep: bool = False
    #: A process that must not be running while this directory is moved.
    guard: str = ""
    #: Shell command run inside the directory after a fresh clone, such as
    #: "make install" for a repository that has to be built.
    build: str = ""

    @property
    def is_repo(self) -> bool:
        return bool(self.url)

    @property
    def name(self) -> str:
        """Last path component, used in messages."""
        return self.path.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Config:
    """Everything ~/42.toml can express."""

    git_name: str = ""
    git_email: str = ""
    resolution: str = ""
    output: str = ""
    gnome_tweaks: bool = False
    tools: list[str] = field(default_factory=list)
    browser_repo: str = ""
    extensions: dict[str, str] = field(default_factory=dict)
    vscode_settings: dict[str, str] = field(default_factory=dict)
    dirs: list[Directory] = field(default_factory=list)
    #: Android API level to install. Flutter raises its minimum over time, so
    #: this is a setting rather than a constant in the code.
    android_api: int = 36

    @property
    def goinfre(self) -> Path:
        return Path("/goinfre") / os.environ["USER"]

    @property
    def tools_dir(self) -> Path:
        return self.goinfre / "tools"

    def resolve(self, entry: Directory) -> Path:
        """Absolute path of a managed directory on goinfre."""
        return self.goinfre / entry.path

    def resolve_link(self, entry: Directory) -> Path | None:
        """Absolute path of the symlink in $HOME, or None when there is none."""
        return Path.home() / entry.link if entry.link else None


def load(path: Path = CONFIG_FILE) -> Config:
    """Read ~/42.toml, using defaults for anything absent."""
    ensure_file(path)

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    git = raw.get("git", {})
    display = raw.get("display", {})
    tools = raw.get("tools", {})
    browser = raw.get("browser", {})

    return Config(
        git_name=git.get("name", ""),
        git_email=git.get("email", ""),
        resolution=display.get("resolution", ""),
        output=display.get("output", ""),
        gnome_tweaks=display.get("gnome_tweaks", False),
        tools=tools.get("enabled", []),
        browser_repo=browser.get("backup_repo", ""),
        extensions=raw.get("extensions", {}),
        vscode_settings=raw.get("vscode", {}).get("settings", {}),
        dirs=[Directory(**entry) for entry in raw.get("dirs", [])],
        android_api=raw.get("android", {}).get("api_level", 36),
    )
