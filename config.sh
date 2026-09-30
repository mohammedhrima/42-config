#!/bin/zsh

local script_path="${(%):-%x}"
local current_dir="$(cd -P "$(dirname "$script_path")" && pwd)"
local expected_dir="/goinfre/$USER/42-config"

if [ "$current_dir" != "$expected_dir" ]; then
    echo "❌ Error: 42-config is currently located at: $current_dir"
    echo "➡️ Please move me to $expected_dir:"
    echo "   mv \"$current_dir\" \"$expected_dir\""
    echo ""
    echo "➡️ Or clone me fresh in /goinfre/$USER/:"
    echo "   git clone https://github.com/mohammedhrima/42-config.git \"$expected_dir\""
    return 1
fi

CONFIG="/goinfre/$USER/42-config"
TOOLS="/goinfre/$USER/tools"
REALOCATED="/goinfre/$USER/realocated"

mkdir -p $TOOLS
mkdir -p $REALOCATED

# /goinfre is world-traversable and every workstation is shared, so keep the
# directories that hold personal data readable by their owner only. mkdir -p
# does not change the mode of a directory that already exists.
chmod 700 "$TOOLS" "$REALOCATED" 2>/dev/null

# Per-user private settings: machine-specific values that must not be published
# here. Kept in $HOME because logout wipes /goinfre, so anything stored next to
# this script is gone on the next session, exactly like ~/repos.toml.
CUSTOM="$HOME/.42-custom.sh"

if [ ! -f "$CUSTOM" ]; then
    cat > "$CUSTOM" <<'CUSTOM_EOF'
#!/bin/zsh
# Private settings for 42-config. Not tracked by any repository.

# Private repository holding your ~/.claude directory (conversations, plans,
# skills). While this stays unset, `memo` does nothing and ~/.claude is left
# alone, so the rest of the configuration behaves normally.
# CLAUDE_MEMO_URL="git@github.com:<you>/<your-private-repo>.git"
CUSTOM_EOF
    chmod 600 "$CUSTOM"
    echo "Created $CUSTOM"
fi

source "$CUSTOM"

CLAUDE_DIR="$REALOCATED/.claude"

VSCODE_URL="https://update.code.visualstudio.com/latest/linux-x64/stable"
VSCODE_COMP="$TOOLS/code-installation.tar.gz"
VSCODE_PATH="$TOOLS/code"
VSCODE_BIN="$TOOLS/code/bin"

NODE_URL="https://nodejs.org/dist/latest/$(curl -s https://nodejs.org/dist/latest/ | grep -o 'node-v[0-9.]*-linux-x64\.tar\.xz' | head -n1)"
NODE_COMP="$TOOLS/node-installation.tar.gz"
NODE_PATH="$TOOLS/node"
NODE_BIN="$TOOLS/node/bin"

UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz"
UV_COMP="$TOOLS/uv-installation.tar.gz"
UV_PATH="$TOOLS/uv"
UV_BIN="$TOOLS/uv"

FLUTTER_URL="https://storage.googleapis.com/flutter_infra_release/releases/$(curl -s https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json | grep -o 'stable/linux/flutter_linux_[0-9.]*-stable\.tar\.xz' | head -n1)"
FLUTTER_COMP="$TOOLS/flutter-installation.tar.xz"
FLUTTER_PATH="$TOOLS/flutter"
FLUTTER_BIN="$TOOLS/flutter/bin"

gsettings set org.gnome.shell.extensions.dash-to-dock dash-max-icon-size 32
gsettings set org.gnome.desktop.interface text-scaling-factor 1.0
gsettings set org.gnome.desktop.interface scaling-factor 0

local target_res="2560x1440"
local output_name="eDP"

if xrandr --current | grep -qw "$target_res"; then
    echo "Found $target_res, applying resolution..."
    xrandr --output "$output_name" --mode "$target_res"
fi

# Progress output. Every function below reports through these so a long step
# never looks like a hang.
_step() { echo ""; echo "==> $*" }
_info() { echo "    $*" }
_ok()   { echo "    [ok] $*" }
_err()  { echo "    [!!] $*" >&2 }

_install() {
    local url="$1"
    local archive="$2"
    local install_path="$3"
    local bin_path="$4"
    local name="${install_path:t}"

    if [ -d "$install_path" ]; then
        # _info "$name already installed ($install_path)"
        return 0
    fi

    _step "Installing $name"
    _info "from $url"
    _info "downloading..."

    curl -fL --progress-bar "$url" -o "$archive" || {
        _err "$name: download failed"
        rm -f "$archive"
        return 1
    }
    _ok "downloaded $(du -h "$archive" 2>/dev/null | cut -f1)"

    mkdir -p "$install_path" || return 1

    _info "extracting to $install_path"
    _info "this can take a few minutes, do not interrupt it"
    tar -xf "$archive" --strip-components=1 -C "$install_path" || {
        _err "$name: extract failed"
        rm -rf "$install_path"
        rm -f "$archive"
        return 1
    }

    rm -f "$archive"
    _ok "$name ready, $(du -sh "$install_path" 2>/dev/null | cut -f1) in $install_path"
}

# 2. Put newly installed tool bins at the very front of PATH immediately
export PATH="$NODE_BIN:$VSCODE_BIN:$UV_PATH:$FLUTTER_BIN:$PATH"

# install() {
# _step "Installing tools into $TOOLS"
# 1. Install tools first
_install "$VSCODE_URL" "$VSCODE_COMP" "$VSCODE_PATH" "$VSCODE_BIN" && \
_install "$NODE_URL" "$NODE_COMP" "$NODE_PATH" "$NODE_BIN" && \
_install "$UV_URL" "$UV_COMP" "$UV_PATH" "$UV_BIN" && \
_install "$FLUTTER_URL" "$FLUTTER_COMP" "$FLUTTER_PATH" "$FLUTTER_BIN"

PAPERDESK="$TOOLS/paperdesk"
if [ ! -d "$PAPERDESK" ]; then
    _step "Installing paperdesk"
    git clone git@github.com:mohammedhrima/paperdesk.git $PAPERDESK && \
    make install -C $PAPERDESK && _ok "paperdesk ready"
else
    # _info "paperdesk already installed"
fi

BEEKEEPER_PATH="$TOOLS/beekeeper"
if [ ! -d "$BEEKEEPER_PATH" ]; then
    _step "Installing beekeeper"
    # releases/latest redirects to .../tag/vX.Y.Z. Read the version from there
    # rather than from the GitHub API: the whole cluster shares one public IP,
    # and the API allows 60 unauthenticated calls per hour per IP.
    local bk_version=$(curl -fsIL -o /dev/null -w '%{url_effective}' \
        "https://github.com/beekeeper-studio/beekeeper-studio/releases/latest" | sed -n 's|.*/tag/v||p')
    local bk_stage="$TOOLS/.beekeeper-stage"

    if [ -z "$bk_version" ]; then
        _err "beekeeper: could not find the latest version"
    else
        local bk_url="https://github.com/beekeeper-studio/beekeeper-studio/releases/download/v$bk_version/Beekeeper-Studio-$bk_version.AppImage"
        rm -rf "$bk_stage"
        mkdir -p "$bk_stage"
        _info "from $bk_url"
        _info "downloading..."
        # Extracted once instead of run as an AppImage: running it needs FUSE,
        # which needs sudo, and --appimage-extract-and-run unpacks 1 GB to /tmp
        # on every launch. Extracting in a staging directory means a failed
        # attempt leaves no half-installed $BEEKEEPER_PATH behind.
        if curl -fL --progress-bar "$bk_url" -o "$bk_stage/beekeeper.AppImage" && \
           chmod +x "$bk_stage/beekeeper.AppImage" && \
           _info "extracting to $BEEKEEPER_PATH" && \
           (cd "$bk_stage" && ./beekeeper.AppImage --appimage-extract > /dev/null) && \
           mv "$bk_stage/squashfs-root" "$BEEKEEPER_PATH"; then
            _ok "beekeeper $bk_version ready, $(du -sh "$BEEKEEPER_PATH" 2>/dev/null | cut -f1) in $BEEKEEPER_PATH"
        else
            _err "beekeeper: install failed"
        fi
        rm -rf "$bk_stage"
    fi
fi

# _step "All tools done"
# _info "PATH now starts with: node, code, uv, flutter"
# }


# Dart downloads packages to ~/.pub-cache by default and it grows past a GB.
# $HOME is the small disk, so keep it on goinfre like everything else.
export PUB_CACHE="$REALOCATED/.pub-cache"
rehash

update() {
    source "$CONFIG/config.sh"
    source "$HOME/.zshrc"
}



alias clean="clear"


WORKSPACE_GOINFRE="/goinfre/$USER/workspace"
WORKSPACE_DESKTOP="$HOME/Desktop/workspace"

if [ ! -d "$WORKSPACE_GOINFRE" ]; then
    echo "Created directory at $WORKSPACE_GOINFRE"
    mkdir -p "$WORKSPACE_GOINFRE"
fi

chmod 700 "$WORKSPACE_GOINFRE" 2>/dev/null

if [ ! -L "$WORKSPACE_DESKTOP" ] && [ ! -d "$WORKSPACE_DESKTOP" ]; then
    echo "Created symlink on Desktop pointing to $WORKSPACE_GOINFRE"
    ln -s "$WORKSPACE_GOINFRE" "$WORKSPACE_DESKTOP"
fi

add() {
    if [ -z "$1" ] || [ -z "$2" ]; then
        echo "Usage: add-repo <repo_url> <dir_name>"
        return 1
    fi

    local dir_name="$2"
    local repo_url="$1"
    local target_dir="$WORKSPACE_GOINFRE/$dir_name"
    local tracking_file="$HOME/repos.toml"

    if [ ! -d "$target_dir" ]; then
        _step "Adding $dir_name"
        _info "cloning all branches from $repo_url ..."
        git clone --no-single-branch "$repo_url" "$target_dir" || {
            _err "clone failed"
            return 1
        }
        _ok "cloned into $target_dir"
    else
        _info "$target_dir already exists"
    fi

    if [ ! -f "$tracking_file" ]; then
        echo "[repositories]" > "$tracking_file"
    fi

    if ! grep -q "^$dir_name =" "$tracking_file" 2>/dev/null; then
        echo "$dir_name = \"$repo_url\"" >> "$tracking_file"
        _ok "recorded in $tracking_file"
    fi
}

repos() {
    local tracking_file="$HOME/repos.toml"

    if [ ! -f "$tracking_file" ]; then
        _err "no tracking file at $tracking_file"
        return 1
    fi

    _step "Cloning repositories listed in $tracking_file"

    while IFS='=' read -r key val; do
        local dir_name=$(echo "$key" | xargs)
        local repo_url=$(echo "$val" | xargs | tr -d '"')

        [[ -z "$dir_name" || "$dir_name" == \[* || "$dir_name" == \#* ]] && continue

        local target_dir="$WORKSPACE_GOINFRE/$dir_name"

        if [ ! -d "$target_dir" ]; then
            _info "cloning $dir_name from $repo_url ..."
            git clone --no-single-branch "$repo_url" "$target_dir" || {
                _err "$dir_name: clone failed"
                continue
            }
            _info "creating local branches for $dir_name..."
            
            cd "$target_dir" || continue
            for remote in $(git branch -r | grep -v '\->'); do
                local branch="${remote#origin/}"
                if ! git show-ref --verify --quiet "refs/heads/$branch"; then
                    git checkout -b "$branch" "$remote" 2>/dev/null
                fi
            done
            git checkout main 2>/dev/null || git checkout master 2>/dev/null
            cd - > /dev/null
            _ok "$dir_name ready"
        else
            _info "$dir_name already present, skipping"
        fi
    done < "$tracking_file"
}

space() {
    local relocated_dir="/goinfre/$USER/realocated"
    mkdir -p "$relocated_dir"

    _step "Relocating heavy directories to $relocated_dir"

    # An entry may contain a slash (".config/Code"), so every mkdir/mv below
    # creates the parent first.
    local heavy_dirs=(".cache" ".npm" ".vscode" ".vscode-shared" ".copilot" ".dotnet" ".config/Code")

    for dir in "${heavy_dirs[@]}"; do
        local target_home="$HOME/$dir"
        local target_goinfre="$relocated_dir/$dir"

        # If it's a real directory in home (and not already a symlink)
        if [ -d "$target_home" ] && [ ! -L "$target_home" ]; then
            _info "moving $dir ($(du -sh "$target_home" 2>/dev/null | cut -f1)) to goinfre..."
            mkdir -p "${target_goinfre:h}"
            # If target in goinfre already exists, merge contents or remove conflict
            if [ -d "$target_goinfre" ]; then
                cp -rn "$target_home/"* "$target_goinfre/" 2>/dev/null
                rm -rf "$target_home"
            else
                mv "$target_home" "$target_goinfre"
            fi
            ln -s "$target_goinfre" "$target_home"
            _ok "$dir -> $target_goinfre"
        elif [ ! -e "$target_home" ]; then
            # If it doesn't exist anywhere yet, create it in goinfre and symlink
            mkdir -p "$target_goinfre"
            ln -s "$target_goinfre" "$target_home"
            _ok "$dir created on goinfre and linked"
        else
            _info "$dir already linked"
        fi
    done

    memo
}

# Relocate $HOME/.claude to goinfre like the directories above, except that it
# is a clone of a private repository instead of an empty directory: the
# conversations, plans and skills follow you from one workstation to the next.
#
# Does nothing while CLAUDE_MEMO_URL is unset, which is the case for anyone who
# has not put their own repository in ~/.42-custom.sh.
memo() {
    if [ -z "$CLAUDE_MEMO_URL" ]; then
        return 0
    fi

    _step "Linking ~/.claude to its private repository"

    local home_claude="$HOME/.claude"

    # A session that ended without logout leaves a link into a wiped goinfre.
    if [ -L "$home_claude" ] && [ ! -e "$home_claude" ]; then
        rm -f "$home_claude"
    fi

    # Already linked: only refresh.
    if [ -L "$home_claude" ] && [ "$(readlink -f "$home_claude")" = "$CLAUDE_DIR" ]; then
        _info "already linked, refreshing..."
        git -C "$CLAUDE_DIR" pull --rebase --autostash 2>/dev/null
        _ok "up to date"
        return 0
    fi

    # Everything below moves the directory Claude Code reads its configuration
    # and session state from, which a running instance would not survive.
    if pgrep -u "$USER" -x claude > /dev/null 2>&1; then
        _err "Claude Code is running. Close it, then run 'memo' again"
        return 1
    fi

    if [ ! -d "$CLAUDE_DIR/.git" ]; then
        if [ -d "$home_claude/.git" ] && [ ! -L "$home_claude" ]; then
            # logout put the clone back in $HOME at the end of the last session.
            _info "found .claude in \$HOME from last session, moving it to goinfre..."
            mv "$home_claude" "$CLAUDE_DIR" || return 1
        else
            [ -e "$CLAUDE_DIR" ] && mv "$CLAUDE_DIR" "$CLAUDE_DIR.broken.$(date +%s)"
            _info "cloning from $CLAUDE_MEMO_URL ..."
            git clone "$CLAUDE_MEMO_URL" "$CLAUDE_DIR" || {
                _err "clone failed, $home_claude left untouched"
                rm -rf "$CLAUDE_DIR"
                return 1
            }
        fi
    fi

    # First run on a machine that already had a real ~/.claude: fold it into the
    # clone. -n keeps whatever the repository already carries, so settings and
    # conversations pushed from another workstation win. The login token is the
    # exception: the local one is the live one.
    if [ -d "$home_claude" ] && [ ! -L "$home_claude" ]; then
        _info "merging your existing $home_claude into the clone..."
        cp -a -n "$home_claude/." "$CLAUDE_DIR/" 2>/dev/null
        [ -f "$home_claude/.credentials.json" ] && \
            cp -a -f "$home_claude/.credentials.json" "$CLAUDE_DIR/.credentials.json"
        mv "$home_claude" "$home_claude.bak.$(date +%Y%m%d%H%M%S)" || return 1
    fi

    # After the copy, never before: cp -a carries the mode of the directory it
    # copied from, which would put the clone back to 755.
    chmod 700 "$CLAUDE_DIR"

    ln -s "$CLAUDE_DIR" "$home_claude"
    _ok "$home_claude -> $CLAUDE_DIR"
    _info "refreshing from the remote..."

    # Best effort: the link is what matters, a failed refresh is not a failure.
    git -C "$CLAUDE_DIR" pull --rebase --autostash 2>/dev/null
    return 0
}

# Commit and push the .claude clone. Called by logout, and safe to run by hand.
memo_save() {
    if [ -z "$CLAUDE_MEMO_URL" ] || [ ! -d "$CLAUDE_DIR/.git" ]; then
        return 0
    fi

    # The repository's .gitignore is what keeps per-session state and IDE lock
    # files out of the history. If it is missing or was replaced, `git add -A`
    # below would publish them, so stop instead.
    _step "Pushing ~/.claude"
    _info "checking that session state is still ignored..."

    local leak
    for leak in sessions ide backups shell-snapshots session-env cache plugins; do
        if ! git -C "$CLAUDE_DIR" check-ignore -q "$leak"; then
            _err "'$leak' is not ignored by $CLAUDE_DIR/.gitignore, refusing to push"
            return 1
        fi
    done

    git -C "$CLAUDE_DIR" add -A
    local changed=$(git -C "$CLAUDE_DIR" diff --cached --numstat | wc -l | tr -d ' ')
    if [ -n "$(git -C "$CLAUDE_DIR" status --porcelain)" ]; then
        _info "committing $changed changed file(s)..."
        git -C "$CLAUDE_DIR" commit -q -m "memo: $(date '+%Y-%m-%d %H:%M:%S') ($(hostname -s))"
    else
        _info "nothing new to commit"
    fi

    _info "rebasing on the remote..."
    git -C "$CLAUDE_DIR" pull --rebase --autostash || {
        _err "rebase failed, fix it by hand in $CLAUDE_DIR"
        return 1
    }

    _info "pushing..."
    git -C "$CLAUDE_DIR" push || {
        _err "push failed, $CLAUDE_DIR is kept (logout will move it to \$HOME)"
        return 1
    }
    _ok "pushed"
}

# Start Beekeeper Studio detached from the terminal, so the prompt comes back
# and closing the terminal does not close the app.
beekeeper() {
    if [ ! -x "$BEEKEEPER_PATH/AppRun" ]; then
        _err "beekeeper is not installed, run 'update' to install it"
        return 1
    fi
    "$BEEKEEPER_PATH/AppRun" "$@" > /dev/null 2>&1 &!
}

EXTENSIONS_TOML="$HOME/extensions.toml"

# Set one key in VS Code's settings.json. That file is JSONC: it allows comments
# and trailing commas, so it is edited as text. Parsing and rewriting it as JSON
# would silently delete every comment in it.
_vscode_setting() {
    local key="$1"
    local value="$2"
    local f="$HOME/.config/Code/User/settings.json"

    mkdir -p "${f:h}"
    [ -f "$f" ] || echo '{}' > "$f"

    VS_KEY="$key" VS_VAL="$value" VS_FILE="$f" python3 <<'PYEOF'
import os, re
key, val, path = os.environ["VS_KEY"], os.environ["VS_VAL"], os.environ["VS_FILE"]
lines = open(path).readlines()
pat = re.compile(r'^(\s*)"' + re.escape(key) + r'"(\s*:\s*)"[^"]*"(.*)$')
for i, line in enumerate(lines):
    if line.lstrip().startswith("//"):
        continue
    m = pat.match(line)
    if m:
        new = '%s"%s"%s"%s"%s\n' % (m.group(1), key, m.group(2), val, m.group(3))
        if new == line:
            print("    %s already set to %s" % (key, val))
        else:
            lines[i] = new
            open(path, "w").writelines(lines)
            print("    [ok] %s = %s" % (key, val))
        break
else:
    for i, line in enumerate(lines):
        if "{" in line:
            lines.insert(i + 1, '  "%s": "%s",\n' % (key, val))
            open(path, "w").writelines(lines)
            print("    [ok] %s = %s (added)" % (key, val))
            break
PYEOF
}

# VS Code extensions, tracked in ~/extensions.toml exactly the way repos.toml
# tracks repositories: the file lives in $HOME so it survives the goinfre wipe,
# and the extensions themselves land in ~/.vscode/extensions, which `space`
# already relocated to goinfre.
#
#   ext              install everything listed, then apply the theme
#   ext add <id>     add one extension to the list and install it
#   ext rm <id>      drop one from the list (does not uninstall it)
#   ext save         overwrite the list with whatever is installed right now
#   ext list         show which listed extensions are installed
ext() {
    local code_bin="$VSCODE_BIN/code"

    if [ ! -x "$code_bin" ]; then
        _err "vscode is not installed, run 'install' first"
        return 1
    fi

    if [ ! -f "$EXTENSIONS_TOML" ]; then
        _info "creating $EXTENSIONS_TOML"
        echo "[extensions]" > "$EXTENSIONS_TOML"
    fi

    local name id installed lower

    case "$1" in
        add)
            shift
            if [ -z "$1" ]; then
                _err "usage: ext add <publisher.extension>"
                return 1
            fi
            id="$1"
            name="${2:-${id##*.}}"
            if grep -qi "\"$id\"" "$EXTENSIONS_TOML"; then
                _info "$id already listed"
            else
                echo "$name = \"$id\"" >> "$EXTENSIONS_TOML"
                _ok "added $id to $EXTENSIONS_TOML"
            fi
            _step "Installing $id"
            "$code_bin" --install-extension "$id" --force 2>&1 | sed 's/^/    /'
            ;;

        rm)
            shift
            if [ -z "$1" ]; then
                _err "usage: ext rm <publisher.extension>"
                return 1
            fi
            grep -vi "\"$1\"" "$EXTENSIONS_TOML" > "$EXTENSIONS_TOML.tmp" && \
                mv "$EXTENSIONS_TOML.tmp" "$EXTENSIONS_TOML"
            _ok "$1 removed from the list"
            _info "still installed. To remove it: code --uninstall-extension $1"
            ;;

        save)
            _step "Saving installed extensions to $EXTENSIONS_TOML"
            echo "[extensions]" > "$EXTENSIONS_TOML"
            for id in $("$code_bin" --list-extensions 2>/dev/null); do
                echo "${id##*.} = \"$id\"" >> "$EXTENSIONS_TOML"
                _info "$id"
            done
            _ok "saved"
            ;;

        list)
            _step "Extensions listed in $EXTENSIONS_TOML"
            installed=$("$code_bin" --list-extensions 2>/dev/null | tr 'A-Z' 'a-z')
            while IFS='=' read -r name id; do
                name=$(echo "$name" | xargs)
                id=$(echo "$id" | xargs | tr -d '"')
                [[ -z "$name" || "$name" == \[* || "$name" == \#* ]] && continue
                lower=$(echo "$id" | tr 'A-Z' 'a-z')
                if echo "$installed" | grep -qx "$lower"; then
                    _ok "$id"
                else
                    _info "$id  NOT INSTALLED"
                fi
            done < "$EXTENSIONS_TOML"
            ;;

        *)
            _step "Installing extensions from $EXTENSIONS_TOML"
            installed=$("$code_bin" --list-extensions 2>/dev/null | tr 'A-Z' 'a-z')
            while IFS='=' read -r name id; do
                name=$(echo "$name" | xargs)
                id=$(echo "$id" | xargs | tr -d '"')
                [[ -z "$name" || "$name" == \[* || "$name" == \#* ]] && continue

                lower=$(echo "$id" | tr 'A-Z' 'a-z')
                if echo "$installed" | grep -qx "$lower"; then
                    _info "$id already installed"
                else
                    _info "installing $id ..."
                    if "$code_bin" --install-extension "$id" --force > /dev/null 2>&1; then
                        _ok "$id"
                    else
                        _err "$id failed to install"
                    fi
                fi
            done < "$EXTENSIONS_TOML"

            _step "Applying theme"
            _vscode_setting "workbench.colorTheme" "One Dark Pro Night Flat"
            _vscode_setting "workbench.iconTheme" "material-icon-theme"
            ;;
    esac
}

mouse() {
    while true; do
        xdotool mousemove_relative -- 1 0
        # Sleep for 5 minutes (5 * 60 = 300 seconds)
        sleep 300
    done
}

logout() {
    _step "Pushing workspace repositories"
    # 1. Sync and push all workspace repositories (with null-glob modifier to prevent errors if empty)
    if [ -d "$WORKSPACE_GOINFRE" ]; then
        for repo in "$WORKSPACE_GOINFRE"/*(/N) ; do
            if [ -d "$repo/.git" ]; then
                cd "$repo" || continue
                if [[ -n $(git status -s) ]] || [[ -n $(git cherry -v 2>/dev/null) ]]; then
                    _info "pushing ${repo:t}..."
                    git add .
                    git commit -m "Autosync on session logout: $(date)"
                    git push && _ok "${repo:t} pushed" || _err "${repo:t} push FAILED"
                else
                    _info "${repo:t} already clean"
                fi
            fi
        done
    fi

    # # 2. Sync and push changes in the 42-config repository
    # local config_dir="/goinfre/$USER/42-config"
    # if [ -d "$config_dir/.git" ]; then
    #     cd "$config_dir" || return 1
    #     if [[ -n $(git status -s) ]] || [[ -n $(git cherry -v 2>/dev/null) ]]; then
    #         git add .
    #         git commit -m "Autosync 42-config on logout: $(date)"
    #         git push
    #     fi
    # fi

    # 3. Push the .claude clone. No-op unless CLAUDE_MEMO_URL is set.
    memo_save

    # 4. Restore heavy files back to $HOME from goinfre before wiping.
    #    .claude is restored like the rest: if the push above failed, the clone
    #    is still in $HOME on the next session instead of being wiped, and the
    #    login token travels with it so there is no login to redo.
    _step "Restoring directories to \$HOME"
    local relocated_dir="/goinfre/$USER/realocated"
    local heavy_dirs=(".cache" ".npm" ".vscode" ".vscode-shared" ".copilot" ".dotnet" ".config/Code" ".claude")

    for dir in "${heavy_dirs[@]}"; do
        local target_home="$HOME/$dir"
        local target_goinfre="$relocated_dir/$dir"

        if [ -L "$target_home" ]; then
            rm "$target_home"
            if [ -d "$target_goinfre" ]; then
                _info "moving $dir back to \$HOME..."
                mkdir -p "${target_home:h}"
                mv "$target_goinfre" "$target_home" && _ok "$dir restored"
            else
                _info "$dir: link removed, nothing on goinfre to restore"
            fi
        fi
    done

    _step "Wiping goinfre"
    # 5. Wipe temporary goinfre runtime storage
    _info "removing tools, 42-config, workspace and realocated..."
    rm -rf "$TOOLS"
    rm -rf "$CONFIG"
    rm -rf "$WORKSPACE_GOINFRE"
    rm -rf "$relocated_dir"
    _ok "goinfre clean. Safe to log out."
}