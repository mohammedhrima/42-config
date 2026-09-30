# 42-config

A development environment for 42 / 1337 workstations, where `/goinfre` is wiped
between sessions and `$HOME` is small.

It keeps heavy directories on `/goinfre`, installs your tools without root,
restores your repositories on any workstation, and pushes everything before the
machine is wiped.

Everything personal lives in `~/42.toml`, which is not part of this repository.
Nothing in here refers to any particular person, machine or repository.

---

## The one thing to understand first

`/goinfre` is **local to each workstation** and is wiped when you change post.

Anything you put there is gone unless it is either pushed to a git remote or
marked `keep = true` so `42 logout` moves it into `$HOME` first. `$HOME` follows
you between workstations; `/goinfre` does not.

Get this wrong and you lose data. Most of this configuration exists to get it
right for you.

---

## Install

Clone it and add the bootstrap to `~/.zshrc`:

```sh
CONFIG="/goinfre/$USER/42-config"
CONFIG_URL="https://github.com/<owner>/42-config.git"

login() {
    if [ ! -d "$CONFIG" ]; then
        git clone "$CONFIG_URL" "$CONFIG" || return 1
    fi
    source "$CONFIG/config.sh" && 42 space
}

if [ -d "$CONFIG" ]; then
    source "$CONFIG/config.sh"
fi
```

Then, on a new workstation, run `login` once. Later terminals pick it up by
themselves.

The repository must sit at `/goinfre/$USER/42-config`; `config.sh` refuses to run
from anywhere else, because everything is relative to that path.

Requirements: `zsh`, `python3` 3.11 or newer, `git`, `curl`. All present on a 42
workstation.

---

## Commands

Run `42 --help` for the current list.

| Command | What it does |
|---|---|
| `42 space` | Put everything where it belongs on this workstation. Run once per session. |
| `42 install --all` | Download every tool listed in `~/42.toml`. |
| `42 install uv node` | Install those tools and remember them for next time. |
| `42 add <url> <path>` | Register a repository and clone it. |
| `42 ext` | Install the VS Code extensions you listed. |
| `42 ext add <publisher.name>` | Add one extension and install it. |
| `42 ext save` | Replace the list with whatever is installed now. |
| `42 gcache save` / `load` | Back up or restore the Chrome profile. |
| `42 logout` | Push everything, free the disk, wipe `/goinfre`. |
| `42 update` | Re-read `config.sh` after editing it. |
| `42 mouse` | Nudge the pointer so the session does not lock. |

`logout` also works on its own, since it is typed every session.

---

## `~/42.toml`

Created on first run. It is the only file you edit.

```toml
[git]
# A workstation has no git identity, so git invents $USER@$HOST and every post
# authors commits under a different address.
name  = "<your name>"
email = "<your@email>"

[display]
resolution   = "2560x1440"   # empty = do not touch the display
output       = "eDP"
gnome_tweaks = false         # true also sets dock size and scaling

[tools]
# code, node, uv, flutter, ninja, android, beekeeper
enabled = ["code", "node", "uv"]

[browser]
backup_repo = ""             # private repo for the Chrome profile; empty = off

[extensions]
# 42 ext add <publisher.name> writes here
python = "ms-python.python"

[vscode.settings]
# Written into settings.json, keeping your comments
"workbench.colorTheme" = "Default Dark Modern"
```

---

## Managed directories

One concept covers caches, work repositories and private configuration.

```toml
[[dirs]]
path  = "realocated/.cache"    # where it lives under /goinfre/$USER
link  = ".cache"               # symlink this $HOME path to it
```

```toml
[[dirs]]
path = "workspace/my-project"
url  = "git@github.com:<owner>/my-project.git"
```

```toml
[[dirs]]
path  = "realocated/.config/nvim"
link  = ".config/nvim"
url   = "git@github.com:<owner>/nvim-config.git"
keep  = true                   # logout carries it into $HOME
guard = "nvim"                 # refuse to move it while nvim runs
build = "make install"         # run this after a fresh clone
```

| Field | Meaning |
|---|---|
| `path` | Location under `/goinfre/$USER`. Required. |
| `url` | Clone from here. Absent means create an empty directory. |
| `link` | `$HOME` path to symlink to it. Absent means no symlink. |
| `keep` | `logout` moves it into `$HOME` instead of letting it be wiped. |
| `guard` | A process that must not be running while it is moved. |
| `build` | Command run inside it after a fresh clone. |

`path` plus `link` is a cache. Add `url` and it is a clone. Add `keep` and it
survives the wipe.

Add entries with `42 add`, or by editing the file.

### First run on a machine that already has the directory

The existing directory is merged into the clone and then **renamed**, never
deleted, to `<name>.bak.<timestamp>`. What the repository already holds wins, so
data pushed from another workstation is not overwritten by a local stub.

For files that belong to this machine rather than the repository, such as a login
token:

```sh
42 space --prefer-local .credentials.json
```

---

## What `42 logout` does, and in what order

The order matters and is not obvious.

1. Save VS Code's settings out of a directory that is otherwise cache.
2. **Drop caches.** Before anything is pushed, not after: running out of disk in
   the middle of a push is the one failure here that loses work.
3. Push every registered repository.
4. Back up the browser profile, if configured.
5. Stop every container and prune Docker's images, volumes and build cache.
6. Delete the remaining caches and the tools, which are all re-downloadable.
7. Move every `keep` directory into `$HOME`, checking there is room first.
8. Wipe `/goinfre`, Docker's data root included.

If something is **not pushed and does not fit in `$HOME`**, it stops at step 7,
leaves your data on `/goinfre`, and tells you so. It will not wipe a disk holding
the only copy of something.

**Docker is wiped.** Images, containers and named volumes all go. They live on
`/goinfre`, so they were never going to survive changing post anyway, but note
that a volume holding something you care about is destroyed. Copy it out first.

---

## Layout

```text
/goinfre/$USER/
├── 42-config/     this repository
├── tools/         code, node, uv, ... re-downloaded per workstation
├── realocated/    directories moved out of $HOME
└── workspace/     your repositories

$HOME/
├── 42.toml        your settings, the only file you edit
└── .zshrc         the bootstrap above
```

```text
42-config/
├── config.sh      45 lines: PATH, environment, the `42` function
└── lib/           everything else, in Python
```

`config.sh` is small on purpose. Only a sourced script can change the shell's
`PATH` and define its functions, so that is all it does. Run `42 env` to see
exactly what it exports; only tools that are actually installed are added, so a
missing one cannot break your `PATH`.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `command not found: 42` | Terminal older than the last change. Run `42 update` or open a new one. |
| `<process> is running. Close it` | A `guard` directory is about to move. Close that program. |
| `42-config must live in ...` | Move the repository to `/goinfre/$USER/42-config`. |
| `<name>.bak.<timestamp>` in `$HOME` | Your directory from before the first merge. Delete it once a full session has worked. |
| An extension will not install | It is not on the marketplace. Use a `[[dirs]]` entry with `build`. |
