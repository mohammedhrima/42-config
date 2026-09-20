# 42-Config

A persistent Zsh environment and workspace manager designed for **42 / 1337 school workstations**.

`42-config` automates the setup of a development environment on machines where the home directory and installed software may not persist between sessions.

It uses `/goinfre/$USER` for persistent storage and provides automatic tool installation, workspace management, repository tracking, disk-space relocation, and session cleanup.

---

## Features

* **Automatic initialization** through a small `.zshrc` configuration.
* **Persistent configuration** stored in `/goinfre/$USER/42-config`.
* **Automatic tool installation**:

  * Visual Studio Code
  * Node.js
  * Astral `uv`
  * Paperdesk
* **Persistent workspace** stored in `/goinfre/$USER/workspace`.
* **Desktop workspace symlink** at `~/Desktop/workspace`.
* **Repository management** through `add` and `repos`.
* **Repository tracking** using `~/repos.toml`.
* **Automatic local branch creation** for remote branches.
* **Disk-space optimization** with `space`.
* **Private per-user settings** in `~/.42-custom.sh`, kept out of this repository.
* **Optional private `~/.claude`** synchronization with `memo`.
* **Automatic Git synchronization** with `logout`.
* **Session cleanup** after logout.
* **Path protection** to ensure the configuration is running from the expected location.

---

# Installation

## 1. Add the bootstrap to `.zshrc`

Add the following to your `~/.zshrc`:

```zsh
CONFIG="/goinfre/$USER/42-config"
CONFIG_URL="https://github.com/mohammedhrima/42-config.git"

init() {
    cd ~ || return 1
    echo "cloning $CONFIG..."
    if [ ! -d "$CONFIG" ]; then
        git clone "$CONFIG_URL" "$CONFIG" || return 1
    fi
    source "$CONFIG/config.sh"
}

if [ -d "$CONFIG" ]; then
    echo "$CONFIG already exists"
    source "$CONFIG/config.sh"
fi
```

The bootstrap uses HTTPS to clone `42-config`, so an SSH key is **not required to initialize the configuration**.

---

## 2. Initialize 42-Config

Reload your Zsh configuration:

```bash
source ~/.zshrc
```

Then run:

```bash
init
```

If `/goinfre/$USER/42-config` does not exist, `init` clones:

```text
https://github.com/mohammedhrima/42-config.git
```

into:

```text
/goinfre/$USER/42-config
```

and loads:

```text
/goinfre/$USER/42-config/config.sh
```

If the directory already exists, `init` simply sources the existing configuration.

---

## 3. Subsequent sessions

On future sessions, the following block in `.zshrc` automatically loads the existing configuration:

```zsh
if [ -d "$CONFIG" ]; then
    echo "$CONFIG already exists"
    source "$CONFIG/config.sh"
fi
```

You therefore do not need to run `init` every time.

---

# Directory Structure

The environment uses `/goinfre/$USER` as its persistent storage area:

```text
/goinfre/$USER/
├── 42-config/
├── tools/
├── realocated/
└── workspace/
```

Your home directory keeps the files that must survive the session cleanup:

```text
$HOME/
├── repos.toml        tracked repositories
└── .42-custom.sh     private settings, mode 600
```

---

# Configuration

The configuration repository must be located at:

```text
/goinfre/$USER/42-config
```

When `config.sh` is sourced, it checks its own location.

If it is not running from the expected directory, it prints instructions to either move the repository or clone a fresh copy into `/goinfre/$USER/42-config`.

This prevents the configuration from operating from an unexpected location.

---

# Automatic Tool Installation

When the configuration is loaded, missing tools are automatically downloaded and installed under:

```text
/goinfre/$USER/tools
```

The installation directories are:

```text
/goinfre/$USER/tools/
├── code/
├── node/
├── uv/
└── paperdesk/
```

The installer only installs a tool when its installation directory does not already exist.

---

## Visual Studio Code

The latest stable Linux x64 version of Visual Studio Code is downloaded and installed into:

```text
/goinfre/$USER/tools/code
```

---

## Node.js

The latest Linux x64 Node.js release is detected automatically and installed into:

```text
/goinfre/$USER/tools/node
```

---

## uv

Astral's `uv` is installed into:

```text
/goinfre/$USER/tools/uv
```

---

## PATH

After installation, the tool directories are added to the beginning of `PATH`:

```text
node
VS Code
uv
existing PATH
```

The shell is then rehashed so the commands are immediately available.

---

## Paperdesk

If Paperdesk is not already installed, it is automatically cloned and installed:

```text
/goinfre/$USER/tools/paperdesk
```

The installation uses:

```bash
git clone git@github.com:mohammedhrima/paperdesk.git
make install -C /goinfre/$USER/tools/paperdesk
```

> Paperdesk itself is cloned through SSH, so GitHub SSH authentication may be required for this step.

---

# Workspace

The persistent workspace is:

```text
/goinfre/$USER/workspace
```

It is automatically created when the configuration is loaded.

A symbolic link is also created on the Desktop:

```text
~/Desktop/workspace
        │
        └── → /goinfre/$USER/workspace
```

This means you can access your projects normally from:

```text
~/Desktop/workspace
```

while the actual files are stored in `/goinfre`.

The Desktop symlink is only created if `~/Desktop/workspace` does not already exist as either a directory or symbolic link.

---

# Repository Management

`42-config` keeps track of your projects using:

```text
~/repos.toml
```

This allows your repository list to survive the cleanup performed at logout.

---

## `add`

Add a repository to your workspace.

### Usage

```bash
add <repo_url> <dir_name>
```

Example:

```bash
add git@github.com:mohammedhrima/ura-lang.git ura-lang
```

The repository will be cloned into:

```text
/goinfre/$USER/workspace/ura-lang
```

and registered in:

```text
~/repos.toml
```

### Example

```bash
add https://github.com/user/project.git project
```

Result:

```text
/goinfre/$USER/workspace/project
```

and:

```toml
[repositories]
project = "https://github.com/user/project.git"
```

The repository is cloned using:

```bash
git clone --no-single-branch
```

so its remote branches are available locally.

If the target directory already exists, the repository is not cloned again.

---

# `repos`

Restore all repositories registered in:

```text
~/repos.toml
```

Usage:

```bash
repos
```

For each repository that does not already exist, `repos`:

1. Clones the repository.
2. Retrieves its remote branches.
3. Creates local branches corresponding to those remote branches.
4. Checks out `main`.
5. Falls back to `master` if `main` does not exist.

For example, if the remote contains:

```text
origin/main
origin/dev
origin/feature/login
```

the command creates:

```text
main
dev
feature/login
```

as local branches.

Repositories that already exist in the workspace are skipped.

---

# Repository Configuration

The tracking file is:

```text
~/repos.toml
```

Example:

```toml
[repositories]
ura-lang = "git@github.com:mohammedhrima/ura-lang.git"
project-a = "git@github.com:user/project-a.git"
project-b = "https://github.com/user/project-b.git"
```

The file is stored in `$HOME` rather than `/goinfre` so that it survives the session cleanup.

---

# Private settings

This repository is public, and `logout` deletes everything under `/goinfre/$USER`, including this repository. A file placed next to `config.sh` and excluded with `.gitignore` would therefore be gone on the next session.

Anything private or machine-specific belongs in:

```text
~/.42-custom.sh
```

It is created with mode `600` the first time `config.sh` runs, containing only comments, and is sourced on every load. An empty one changes nothing, so the configuration behaves identically for anyone who never edits it.

Recognised settings:

```sh
# Private repository holding your ~/.claude directory.
# Leave it unset and `memo` does nothing.
CLAUDE_MEMO_URL="git@github.com:<you>/<your-private-repo>.git"
```

---

# `memo`

`memo` relocates `~/.claude` to `/goinfre/$USER/realocated/.claude` like the directories handled by `space`, except that it is a clone of a private repository rather than an empty directory. Your Claude Code conversations, plans and skills then follow you from one workstation to the next.

It does nothing while `CLAUDE_MEMO_URL` is unset.

Usage:

```bash
memo
```

`space` calls it, so `init` sets it up along with everything else.

On the first run the existing `~/.claude` is merged into the clone and then kept as `~/.claude.bak.<timestamp>`. Nothing is deleted. Files the repository already carries win, so settings pushed from another workstation are preserved; the local login token is the exception, since it is the one that currently works.

`memo` refuses to run while Claude Code is open, because it moves the directory Claude reads its state from. If the clone fails, `~/.claude` is left exactly as it was.

## `memo_save`

```bash
memo_save
```

Commits the clone, rebases onto the remote and pushes. `logout` runs it.

Which files are tracked is decided by the `.gitignore` **inside your private repository**, not by this one. The recommended form denies everything and whitelists what is worth keeping:

```text
/*
!/.gitignore
!/settings.json
!/projects/
!/plans/
!/skills/
```

This keeps caches, plugins, IDE lock files and per-session state out of the history. `memo_save` verifies those rules before every push and refuses to push if they are missing, so a lost `.gitignore` cannot publish session state.

---

# Disk Space Management

## `space`

The `space` command relocates large development directories from `$HOME` to `/goinfre`.

Usage:

```bash
space
```

Currently managed directories are:

```text
.cache
.npm
.vscode
.vscode-shared
.copilot
.dotnet
```

The destination is:

```text
/goinfre/$USER/realocated
```

For example:

```text
$HOME/.npm
```

becomes:

```text
/goinfre/$USER/realocated/.npm
```

and:

```text
$HOME/.npm
```

becomes a symbolic link pointing to the relocated directory.

Conceptually:

```text
$HOME/.npm
      │
      └── symlink ──→ /goinfre/$USER/realocated/.npm
```

This allows applications to continue using their normal `$HOME` paths while the actual data is stored in `/goinfre`.

The command only moves directories that exist and are not already symbolic links.

Finally, `space` calls [`memo`](#memo), which relocates `~/.claude` the same way when `CLAUDE_MEMO_URL` is configured and does nothing otherwise.

---

# `update`

Reload the current configuration without opening a new shell:

```bash
update
```

This is equivalent to:

```bash
source /goinfre/$USER/42-config/config.sh
```

Useful after modifying `config.sh`.

---

# `clean`

The configuration also provides:

```bash
clean
```

which is an alias for:

```bash
clear
```

---

# `logout`

`logout` synchronizes your workspace and cleans the workstation environment.

Usage:

```bash
logout
```

## 1. Synchronize repositories

Every Git repository directly inside:

```text
/goinfre/$USER/workspace
```

is checked.

If a repository has:

* uncommitted changes, or
* unpushed commits,

the script runs:

```bash
git add .
git commit -m "Autosync on session logout: <timestamp>"
git push
```

This allows your work to be pushed before the local workspace is removed.

---

## 2. Push the private `~/.claude` repository

`logout` then runs [`memo_save`](#memo_save), which commits and pushes the `.claude` clone. This step does nothing unless `CLAUDE_MEMO_URL` is set.

---

## 3. Restore relocated directories to `$HOME`

If `space` was previously used, `logout` removes each symbolic link from `$HOME` and moves the real directory back out of `/goinfre`:

```text
$HOME/.cache
$HOME/.npm
$HOME/.vscode
$HOME/.vscode-shared
$HOME/.copilot
$HOME/.dotnet
$HOME/.claude
```

Only symbolic links are replaced this way.

Because `.claude` is restored rather than wiped, a failed push in step 2 costs nothing: the clone is waiting in `$HOME` on the next session, and `memo` moves it back to `/goinfre` instead of cloning again. The login token travels with it, so there is no login to redo.

---

## 4. Remove temporary environment

Finally, `logout` removes:

```text
/goinfre/$USER/tools
/goinfre/$USER/42-config
/goinfre/$USER/workspace
/goinfre/$USER/realocated
```

This leaves the workstation environment clean.

On the next session, the `.zshrc` bootstrap can clone `42-config` again and rebuild the environment.

---

# Typical Workflow

## First setup

Add the bootstrap to `~/.zshrc`:

```zsh
CONFIG="/goinfre/$USER/42-config"
CONFIG_URL="https://github.com/mohammedhrima/42-config.git"

init() {
    cd ~ || return 1
    echo "cloning $CONFIG..."
    if [ ! -d "$CONFIG" ]; then
        git clone "$CONFIG_URL" "$CONFIG" || return 1
    fi
    source "$CONFIG/config.sh"
}

if [ -d "$CONFIG" ]; then
    echo "$CONFIG already exists"
    source "$CONFIG/config.sh"
fi
```

Then:

```bash
source ~/.zshrc
init
```

---

## Free disk space

```bash
space
```

---

## Add a project

```bash
add git@github.com:mohammedhrima/ura-lang.git ura-lang
```

Your project is now available at:

```text
~/Desktop/workspace/ura-lang
```

---

## Restore projects

```bash
repos
```

---

## Update the configuration

```bash
update
```

---

## End the session

```bash
logout
```

The repositories are synchronized and the temporary environment is removed.

---

# Architecture

```text
                         ~/.zshrc
                            │
                            ▼
                          init
                            │
                            ▼
              /goinfre/$USER/42-config
                            │
                            ▼
                       config.sh
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
       tools/           workspace/       realocated/
          │                 │                 │
     ┌────┼────┐            │          ┌──────┼──────┐
     │    │    │            │          │      │      │
    code node  uv        projects     .cache  .npm   ...
          │                 │
          │                 │
          └─────────────────┘
                    │
                    ▼
          ~/Desktop/workspace
                 symlink
```

Persistent repository metadata:

```text
$HOME/repos.toml
```

Temporary/persistent workstation data:

```text
/goinfre/$USER/
├── 42-config
├── tools
├── workspace
└── realocated
```

At logout, the `/goinfre` environment is cleaned and `~/repos.toml` remains available for the next session.

---

# Requirements

The environment requires:

* Zsh
* Git
* `curl`
* `tar`
* standard Unix utilities
* Internet access

GitHub authentication is required for repositories that use SSH URLs.

The initial `42-config` bootstrap uses HTTPS, so it does not require SSH authentication.

---

# Important Notes

* `42-config` must be located at `/goinfre/$USER/42-config`.
* The configuration automatically installs tools that are missing.
* `add` clones repositories using `--no-single-branch`.
* `repos` additionally creates local branches for remote branches.
* `repos` skips repositories that already exist.
* `space` moves only the predefined heavy directories.
* `logout` only scans Git repositories directly inside `workspace`.
* `logout` performs `git push`, so repositories must have working Git authentication.
* `logout` deletes the local `42-config` repository itself.
* `~/repos.toml` is **not** deleted by `logout`.
* On the next session, the `.zshrc` bootstrap can recreate the environment automatically.
