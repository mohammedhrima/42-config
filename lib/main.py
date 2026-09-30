#!/usr/bin/env python3
"""The `42` command.

config.sh defines a single shell function that forwards everything here. The shell
layer stays small because only a sourced script can change the parent shell's PATH
and environment, and that is all it is kept for.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import browser          # noqa: E402
import config as cfg    # noqa: E402
import dirs             # noqa: E402
import extensions       # noqa: E402
import log              # noqa: E402
import system           # noqa: E402
import tomledit         # noqa: E402
import tools            # noqa: E402
import vscode           # noqa: E402


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _vscode_cli(conf: cfg.Config) -> Path | None:
    """Path to the `code` CLI, or None when VS Code is not installed."""
    candidate = tools.TOOLS["code"].bin_path(conf.tools_dir) / "code"
    return candidate if candidate.is_file() else None


def _apply_git_identity(conf: cfg.Config) -> None:
    """Set git's global identity.

    A workstation has none, so git invents $USER@$HOST and every workstation
    authors commits under a different address.
    """
    for key, wanted in (("user.name", conf.git_name), ("user.email", conf.git_email)):
        if not wanted:
            continue
        current = system.git(["config", "--global", key]).stdout.strip()
        if current != wanted:
            system.git(["config", "--global", key, wanted])
            log.ok(f"git {key} = {wanted}")


def _apply_display(conf: cfg.Config) -> None:
    """Apply the display settings, if the user asked for any."""
    if conf.gnome_tweaks:
        for schema, key, value in (
            ("org.gnome.shell.extensions.dash-to-dock", "dash-max-icon-size", "32"),
            ("org.gnome.desktop.interface", "text-scaling-factor", "1.0"),
            ("org.gnome.desktop.interface", "scaling-factor", "0"),
        ):
            system.run(["gsettings", "set", schema, key, value])

    if not conf.resolution or not conf.output:
        return
    available = system.run(["xrandr", "--current"]).stdout
    if conf.resolution in available:
        system.run(["xrandr", "--output", conf.output, "--mode", conf.resolution])
        log.ok(f"display set to {conf.resolution}")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_env(conf: cfg.Config, args: argparse.Namespace) -> int:
    """Print the shell exports for config.sh to eval.

    Only installed tools are added, so a missing one cannot poison PATH.
    """
    entries = []
    for name in conf.tools:
        tool = tools.TOOLS.get(name)
        if tool is None:
            continue
        path = tool.bin_path(conf.tools_dir)
        if path.is_dir():
            entries.append(str(path))

    if entries:
        print(f'export PATH="{":".join(entries)}:$PATH"')

    if "flutter" in conf.tools:
        # Dart writes packages to ~/.pub-cache by default, which grows past a
        # gigabyte on the small $HOME disk.
        print(f'export PUB_CACHE="{conf.goinfre}/realocated/.pub-cache"')

    if "android" in conf.tools:
        android = conf.tools_dir / "android"
        print(f'export ANDROID_HOME="{android}"')
        print(f'export ANDROID_SDK_ROOT="{android}"')
        # Under tools/ and not realocated/ on purpose: logout moves realocated
        # back into $HOME, and emulator images are several GB.
        print(f'export ANDROID_USER_HOME="{conf.tools_dir}/android-home"')
        print(f'export ANDROID_AVD_HOME="{conf.tools_dir}/android-home/avd"')
        print(f'export GRADLE_USER_HOME="{conf.tools_dir}/gradle"')
    return 0


def cmd_install(conf: cfg.Config, args: argparse.Namespace) -> int:
    """`42 install --all` or `42 install uv code`."""
    if args.all or not args.tools:
        wanted = conf.tools
        if not wanted:
            log.info("no tools listed in ~/42.toml. Try: 42 install uv node")
            return 0
    else:
        wanted = args.tools

    unknown = [name for name in wanted if name not in tools.TOOLS]
    if unknown:
        log.err(f"unknown tool(s): {', '.join(unknown)}")
        log.info(f"available: {', '.join(tools.TOOLS)}")
        return 1

    log.step(f"Installing into {conf.tools_dir}")
    failed = [name for name in wanted
              if not tools.install(tools.TOOLS[name], conf.tools_dir)]

    # Naming a tool means wanting it on every workstation, so remember it.
    if not args.all and args.tools:
        added = [name for name in args.tools if name not in conf.tools]
        if added:
            _remember_tools(conf.tools + added)
            log.ok(f"added to ~/42.toml: {', '.join(added)}")

    if failed:
        log.err(f"failed: {', '.join(failed)}")
        return 1
    log.step("All tools done")
    return 0


def _remember_tools(names: list[str]) -> None:
    """Rewrite `[tools] enabled` with `names`, keeping order and dropping repeats."""
    unique = list(dict.fromkeys(names))
    rendered = "enabled = [" + ", ".join(f'"{n}"' for n in unique) + "]"

    lines = cfg.CONFIG_FILE.read_text().splitlines()
    for index, line in enumerate(lines):
        if line.startswith("enabled ="):
            lines[index] = rendered
            cfg.CONFIG_FILE.write_text("\n".join(lines) + "\n")
            return

    # No [tools] table yet: create one at the end.
    lines += ["", "[tools]", rendered]
    cfg.CONFIG_FILE.write_text("\n".join(lines) + "\n")


def cmd_add(conf: cfg.Config, args: argparse.Namespace) -> int:
    """`42 add <url> <path>` - register a repository and clone it."""
    if any(entry.path == args.path for entry in conf.dirs):
        log.info(f"{args.path} is already in ~/42.toml")
    else:
        entry: dict[str, object] = {"path": args.path, "url": args.url}
        if args.link:
            entry["link"] = args.link
        if args.keep:
            entry["keep"] = True
        if args.guard:
            entry["guard"] = args.guard
        tomledit.append_entry(cfg.CONFIG_FILE, "dirs", entry)
        log.ok(f"added {args.path} to ~/42.toml")

    fresh = cfg.load()
    entry_obj = next(e for e in fresh.dirs if e.path == args.path)
    log.step(f"Setting up {args.path}")
    return 0 if dirs.realize(fresh, entry_obj) else 1


def cmd_space(conf: cfg.Config, args: argparse.Namespace) -> int:
    """`42 space` - put everything where it belongs on this workstation."""
    _apply_git_identity(conf)
    _apply_display(conf)

    log.step(f"Setting up directories on {conf.goinfre}")
    conf.tools_dir.mkdir(parents=True, exist_ok=True)
    conf.tools_dir.chmod(0o700)

    failed = 0
    for entry in conf.dirs:
        if not dirs.realize(conf, entry, prefer_local=args.prefer_local):
            failed += 1

    code = _vscode_cli(conf)
    if code is not None:
        extensions.sync(code, conf.extensions)
        vscode.apply_settings(conf.vscode_settings)

    # A fresh workstation has no Chrome profile. Restoring is safe; backing up
    # here is not, because it would overwrite the backup with an empty profile.
    if conf.browser_repo and not browser._profiles(browser.CHROME_DIR):
        browser.load(conf.browser_repo, conf.tools_dir / "browser-backup")

    return 1 if failed else 0


def cmd_gcache(conf: cfg.Config, args: argparse.Namespace) -> int:
    """`42 gcache save|load|list` - the Chrome profile backup."""
    work_dir = conf.tools_dir / "browser-backup"
    action = {
        "save": browser.save,
        "load": browser.load,
        "list": browser.show,
    }[args.action]
    return 0 if action(conf.browser_repo, work_dir) else 1


def cmd_ext(conf: cfg.Config, args: argparse.Namespace) -> int:
    """`42 ext` - VS Code extensions."""
    code = _vscode_cli(conf)
    if code is None:
        log.err("VS Code is not installed. Run: 42 install code")
        return 1

    if args.action == "add":
        status, updated = extensions.add(code, conf.extensions, args.name)
    elif args.action in ("rm", "remove"):
        status, updated = extensions.remove(conf.extensions, args.name)
    elif args.action == "save":
        status, updated = extensions.snapshot(code)
    elif args.action == "list":
        return extensions.show(code, conf.extensions)
    else:
        status = extensions.sync(code, conf.extensions)
        vscode.apply_settings(conf.vscode_settings)
        return status

    if updated != conf.extensions:
        tomledit.set_table(cfg.CONFIG_FILE, "extensions", updated)
        log.ok("~/42.toml updated")
    return status


def cmd_mouse(conf: cfg.Config, args: argparse.Namespace) -> int:
    """`42 mouse` - nudge the pointer so the session does not lock."""
    log.info("nudging the pointer every 5 minutes. Ctrl-C to stop.")
    try:
        while True:
            system.run(["xdotool", "mousemove_relative", "--", "1", "0"])
            time.sleep(300)
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


def cmd_beekeeper(conf: cfg.Config, args: argparse.Namespace) -> int:
    """`42 beekeeper` - launch Beekeeper Studio, detached from this shell."""
    launcher = conf.tools_dir / "beekeeper" / "AppRun"
    if not launcher.is_file():
        log.err("beekeeper is not installed. Run: 42 install beekeeper")
        return 1

    subprocess.Popen(
        [str(launcher)] + args.args,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log.ok("beekeeper started")
    return 0


def cmd_logout(conf: cfg.Config, args: argparse.Namespace) -> int:
    """`42 logout` - push everything, free the disk, wipe goinfre.

    Order matters. Caches are dropped before anything is pushed, because running
    out of space in the middle of a push is the one failure here that loses work.
    """
    log.step("Logout")
    log.info(f"$HOME free: {system.free_mb(Path.home())}M    "
             f"goinfre free: {system.free_mb(conf.goinfre)}M")

    caches = [e for e in conf.dirs if e.link and not e.keep and not e.is_repo]
    repos = [e for e in conf.dirs if e.is_repo]
    keepers = [e for e in conf.dirs if e.keep]

    # VS Code's settings are a few KB inside a directory that is otherwise cache.
    stash = Path.home() / ".42-stash"
    shutil.rmtree(stash, ignore_errors=True)
    settings = Path.home() / ".config" / "Code" / "User"
    if settings.is_dir():
        shutil.copytree(settings, stash / "Code-User")
        log.info("saved VS Code user settings")

    log.step("Freeing cache before pushing")
    for entry in caches:
        dirs.drop(conf, entry)

    if (stash / "Code-User").is_dir():
        settings.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(settings, ignore_errors=True)
        shutil.copytree(stash / "Code-User", settings)
        log.ok("VS Code user settings kept in $HOME")
    shutil.rmtree(stash, ignore_errors=True)
    log.info(f"goinfre free now: {system.free_mb(conf.goinfre)}M")

    log.step("Pushing repositories")
    pushed = {}
    for entry in repos:
        pushed[entry.path] = _push(conf, entry)

    if conf.browser_repo:
        browser.save(conf.browser_repo, conf.tools_dir / "browser-backup")

    log.step("Freeing the rest")
    for entry in conf.dirs:
        if entry.link and not entry.keep and entry.is_repo:
            dirs.drop(conf, entry)
    if conf.tools_dir.is_dir():
        log.info(f"removing {conf.tools_dir} "
                 f"({system.size_mb(conf.tools_dir)}M, all re-downloadable)")
        shutil.rmtree(conf.tools_dir, ignore_errors=True)

    log.step("Keeping what cannot be rebuilt")
    unsafe = []
    for entry in keepers:
        if dirs.carry_back(conf, entry):
            continue
        if pushed.get(entry.path):
            log.info(f"{entry.link or entry.path} is pushed, it will be cloned again")
            dirs.drop(conf, entry)
        else:
            unsafe.append(entry)

    if unsafe:
        for entry in unsafe:
            log.err(f"{entry.path} was NOT pushed and does not fit in $HOME")
        log.err("goinfre will NOT be wiped. Free space in $HOME, then run 42 logout again")
        return 1

    log.step("Wiping goinfre")
    for child in sorted(conf.goinfre.iterdir()):
        if child.name != "docker":       # not ours to delete
            shutil.rmtree(child, ignore_errors=True)
    log.ok(f"goinfre clean. $HOME free: {system.free_mb(Path.home())}M. Safe to log out.")
    return 0


def _push(conf: cfg.Config, entry: cfg.Directory) -> bool:
    """Commit and push one repository. True when the remote has everything."""
    repo = conf.resolve(entry)
    if not (repo / ".git").is_dir():
        return False

    dirty = system.git(["status", "--porcelain"], repo).stdout.strip()
    if dirty:
        log.info(f"committing {entry.name}")
        system.git(["add", "-A"], repo)
        system.git(["commit", "-q", "-m", "autosync on logout"], repo)

    if not system.git_succeeds(["rev-parse", "@{u}"], repo):
        log.info(f"{entry.name} has no upstream, skipping")
        return False

    system.git(["pull", "--rebase", "--autostash"], repo)
    if system.git_succeeds(["push"], repo):
        log.ok(f"{entry.name} pushed")
        return True
    log.err(f"{entry.name} push FAILED")
    return False


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="42",
        description="Development environment for a 42 workstation. "
                    "Settings live in ~/42.toml.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    install = sub.add_parser("install", help="download tools into goinfre")
    install.add_argument("tools", nargs="*", help=f"any of: {', '.join(tools.TOOLS)}")
    install.add_argument("--all", action="store_true",
                         help="install everything listed in ~/42.toml")
    install.set_defaults(handler=cmd_install)

    space = sub.add_parser("space", help="relocate directories and set up this workstation")
    space.add_argument("--prefer-local", nargs="*", default=[], metavar="FILE",
                       help="files where this machine's copy wins over the repository's")
    space.set_defaults(handler=cmd_space)

    add = sub.add_parser("add", help="register a repository and clone it")
    add.add_argument("url")
    add.add_argument("path", help="where to put it, relative to goinfre")
    add.add_argument("--link", help="symlink this $HOME path to it")
    add.add_argument("--keep", action="store_true", help="carry it back to $HOME at logout")
    add.add_argument("--guard", help="process that must not run while it is moved")
    add.set_defaults(handler=cmd_add)

    ext = sub.add_parser("ext", help="VS Code extensions")
    ext.add_argument("action", nargs="?", default="sync",
                     choices=["sync", "add", "rm", "remove", "save", "list"])
    ext.add_argument("name", nargs="?", help="publisher.extension")
    ext.set_defaults(handler=cmd_ext)

    gcache = sub.add_parser("gcache", help="Chrome profile backup")
    gcache.add_argument("action", nargs="?", default="save",
                        choices=["save", "load", "list"])
    gcache.set_defaults(handler=cmd_gcache)

    logout = sub.add_parser("logout", help="push everything, free the disk, wipe goinfre")
    logout.set_defaults(handler=cmd_logout)

    mouse = sub.add_parser("mouse", help="nudge the pointer so the session stays awake")
    mouse.set_defaults(handler=cmd_mouse)

    beekeeper = sub.add_parser("beekeeper", help="launch Beekeeper Studio")
    beekeeper.add_argument("args", nargs="*", help="passed through to Beekeeper")
    beekeeper.set_defaults(handler=cmd_beekeeper)

    env = sub.add_parser("env", help="print shell exports (used by config.sh)")
    env.set_defaults(handler=cmd_env)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 0
    return args.handler(cfg.load(), args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
