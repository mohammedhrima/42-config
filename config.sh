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

gsettings set org.gnome.shell.extensions.dash-to-dock dash-max-icon-size 32
gsettings set org.gnome.desktop.interface text-scaling-factor 1.0
gsettings set org.gnome.desktop.interface scaling-factor 0

local target_res="2560x1440"
local output_name="eDP"

if xrandr --current | grep -qw "$target_res"; then
    echo "Found $target_res, applying resolution..."
    xrandr --output "$output_name" --mode "$target_res"
fi

_install() {
    local url="$1"
    local archive="$2"
    local install_path="$3"
    local bin_path="$4"

    if [ ! -d "$install_path" ]; then
        echo "Installing $install_path..."

        curl -fL "$url" -o "$archive" || return 1
        mkdir -p "$install_path" || return 1
        tar -xf "$archive" --strip-components=1 -C "$install_path" || {
            rm -rf "$install_path"
            rm -f "$archive"
            return 1
        }

        rm -f "$archive"
    else
        # echo "$install_path already exists"
    fi

}

install() {
    # 1. Install tools first
    _install "$VSCODE_URL" "$VSCODE_COMP" "$VSCODE_PATH" "$VSCODE_BIN" && \
    _install "$NODE_URL" "$NODE_COMP" "$NODE_PATH" "$NODE_BIN" && \
    _install "$UV_URL" "$UV_COMP" "$UV_PATH" "$UV_BIN" && \
    PAPERDESK="$TOOLS/paperdesk"
    if [ ! -d "$PAPERDESK" ]; then
        echo "Installing $PAPERDESK..."
        git clone git@github.com:mohammedhrima/paperdesk.git $PAPERDESK && \
        make install -C $PAPERDESK
    fi
}

# 2. Put newly installed tool bins at the very front of PATH immediately
export PATH="$NODE_BIN:$VSCODE_BIN:$UV_PATH:$PATH"
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
        echo "Cloning all branches from $repo_url into $target_dir..."
        git clone --no-single-branch "$repo_url" "$target_dir" || return 1
    else
        echo "Directory $target_dir already exists."
    fi

    if [ ! -f "$tracking_file" ]; then
        echo "[repositories]" > "$tracking_file"
    fi

    if ! grep -q "^$dir_name =" "$tracking_file" 2>/dev/null; then
        echo "$dir_name = \"$repo_url\"" >> "$tracking_file"
        echo "Saved configuration to $tracking_file"
    fi
}

repos() {
    local tracking_file="$HOME/repos.toml"

    if [ ! -f "$tracking_file" ]; then
        echo "No tracking file found at $tracking_file"
        return 1
    fi

    while IFS='=' read -r key val; do
        local dir_name=$(echo "$key" | xargs)
        local repo_url=$(echo "$val" | xargs | tr -d '"')

        [[ -z "$dir_name" || "$dir_name" == \[* || "$dir_name" == \#* ]] && continue

        local target_dir="$WORKSPACE_GOINFRE/$dir_name"

        if [ ! -d "$target_dir" ]; then
            echo "Cloning and setting up all local branches for $dir_name..."
            git clone --no-single-branch "$repo_url" "$target_dir" || continue
            
            cd "$target_dir" || continue
            for remote in $(git branch -r | grep -v '\->'); do
                local branch="${remote#origin/}"
                if ! git show-ref --verify --quiet "refs/heads/$branch"; then
                    git checkout -b "$branch" "$remote" 2>/dev/null
                fi
            done
            git checkout main 2>/dev/null || git checkout master 2>/dev/null
            cd - > /dev/null
        else
            echo "Directory $target_dir already exists, skipping."
        fi
    done < "$tracking_file"
}

space() {
    local relocated_dir="/goinfre/$USER/realocated"
    mkdir -p "$relocated_dir"

    local heavy_dirs=(".cache" ".npm" ".vscode" ".vscode-shared" ".copilot" ".dotnet")

    for dir in "${heavy_dirs[@]}"; do
        local target_home="$HOME/$dir"
        local target_goinfre="$relocated_dir/$dir"

        # If it's a real directory in home (and not already a symlink)
        if [ -d "$target_home" ] && [ ! -L "$target_home" ]; then
            echo "Moving $dir to goinfre..."
            # If target in goinfre already exists, merge contents or remove conflict
            if [ -d "$target_goinfre" ]; then
                cp -rn "$target_home/"* "$target_goinfre/" 2>/dev/null
                rm -rf "$target_home"
            else
                mv "$target_home" "$target_goinfre"
            fi
            ln -s "$target_goinfre" "$target_home"
            echo "Symlinked $dir -> $target_goinfre"
        elif [ ! -e "$target_home" ]; then
            # If it doesn't exist anywhere yet, create it in goinfre and symlink
            mkdir -p "$target_goinfre"
            ln -s "$target_goinfre" "$target_home"
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

    local home_claude="$HOME/.claude"

    # A session that ended without logout leaves a link into a wiped goinfre.
    if [ -L "$home_claude" ] && [ ! -e "$home_claude" ]; then
        rm -f "$home_claude"
    fi

    # Already linked: only refresh.
    if [ -L "$home_claude" ] && [ "$(readlink -f "$home_claude")" = "$CLAUDE_DIR" ]; then
        git -C "$CLAUDE_DIR" pull --rebase --autostash 2>/dev/null
        return 0
    fi

    # Everything below moves the directory Claude Code reads its configuration
    # and session state from, which a running instance would not survive.
    if pgrep -u "$USER" -x claude > /dev/null 2>&1; then
        echo "memo: Claude Code is running, close it and run 'memo' again"
        return 1
    fi

    if [ ! -d "$CLAUDE_DIR/.git" ]; then
        if [ -d "$home_claude/.git" ] && [ ! -L "$home_claude" ]; then
            # logout put the clone back in $HOME at the end of the last session.
            echo "Moving .claude to goinfre..."
            mv "$home_claude" "$CLAUDE_DIR" || return 1
        else
            [ -e "$CLAUDE_DIR" ] && mv "$CLAUDE_DIR" "$CLAUDE_DIR.broken.$(date +%s)"
            echo "Cloning .claude from $CLAUDE_MEMO_URL..."
            git clone "$CLAUDE_MEMO_URL" "$CLAUDE_DIR" || {
                echo "memo: clone failed, $home_claude left untouched"
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
        echo "Merging $home_claude into the clone..."
        cp -a -n "$home_claude/." "$CLAUDE_DIR/" 2>/dev/null
        [ -f "$home_claude/.credentials.json" ] && \
            cp -a -f "$home_claude/.credentials.json" "$CLAUDE_DIR/.credentials.json"
        mv "$home_claude" "$home_claude.bak.$(date +%Y%m%d%H%M%S)" || return 1
    fi

    # After the copy, never before: cp -a carries the mode of the directory it
    # copied from, which would put the clone back to 755.
    chmod 700 "$CLAUDE_DIR"

    ln -s "$CLAUDE_DIR" "$home_claude"
    echo "Linked $home_claude -> $CLAUDE_DIR"

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
    local leak
    for leak in sessions ide backups shell-snapshots session-env cache plugins; do
        if ! git -C "$CLAUDE_DIR" check-ignore -q "$leak"; then
            echo "memo_save: '$leak' is not ignored by $CLAUDE_DIR/.gitignore, refusing to push"
            return 1
        fi
    done

    git -C "$CLAUDE_DIR" add -A
    if [ -n "$(git -C "$CLAUDE_DIR" status --porcelain)" ]; then
        git -C "$CLAUDE_DIR" commit -q -m "memo: $(date '+%Y-%m-%d %H:%M:%S') ($(hostname -s))"
    fi

    git -C "$CLAUDE_DIR" pull --rebase --autostash || {
        echo "memo_save: rebase failed, fix it by hand in $CLAUDE_DIR"
        return 1
    }
    git -C "$CLAUDE_DIR" push || {
        echo "memo_save: push failed, $CLAUDE_DIR is kept"
        return 1
    }
}

mouse() {   
    while true; do
        xdotool mousemove_relative -- 1 0
        # Sleep for 5 minutes (5 * 60 = 300 seconds)
        sleep 300
    done
}

logout() {
    # 1. Sync and push all workspace repositories (with null-glob modifier to prevent errors if empty)
    if [ -d "$WORKSPACE_GOINFRE" ]; then
        for repo in "$WORKSPACE_GOINFRE"/*(/N) ; do
            if [ -d "$repo/.git" ]; then
                cd "$repo" || continue
                if [[ -n $(git status -s) ]] || [[ -n $(git cherry -v 2>/dev/null) ]]; then
                    git add .
                    git commit -m "Autosync on session logout: $(date)"
                    git push
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
    local relocated_dir="/goinfre/$USER/realocated"
    local heavy_dirs=(".cache" ".npm" ".vscode" ".vscode-shared" ".copilot" ".dotnet" ".claude")

    for dir in "${heavy_dirs[@]}"; do
        local target_home="$HOME/$dir"
        local target_goinfre="$relocated_dir/$dir"

        if [ -L "$target_home" ]; then
            rm "$target_home"
            if [ -d "$target_goinfre" ]; then
                mv "$target_goinfre" "$target_home"
            fi
        fi
    done

    # 5. Wipe temporary goinfre runtime storage
    rm -rf "$TOOLS"
    rm -rf "$CONFIG"
    rm -rf "$WORKSPACE_GOINFRE"
    rm -rf "$relocated_dir"
}