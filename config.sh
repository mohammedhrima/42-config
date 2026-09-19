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

# 1. Install tools first
_install "$VSCODE_URL" "$VSCODE_COMP" "$VSCODE_PATH" "$VSCODE_BIN" && \
_install "$NODE_URL" "$NODE_COMP" "$NODE_PATH" "$NODE_BIN" && \
_install "$UV_URL" "$UV_COMP" "$UV_PATH" "$UV_BIN"

# 2. Put newly installed tool bins at the very front of PATH immediately
export PATH="$NODE_BIN:$VSCODE_BIN:$UV_PATH:$PATH"
rehash

update() {
    source "$CONFIG/config.sh"
}

PAPERDESK="$TOOLS/paperdesk"
if [ ! -d "$PAPERDESK" ]; then
    echo "Installing $PAPERDESK..."
    git clone git@github.com:mohammedhrima/paperdesk.git $PAPERDESK && \
    make install -C $PAPERDESK
fi

alias clean="clear"


WORKSPACE_GOINFRE="/goinfre/$USER/workspace"
WORKSPACE_DESKTOP="$HOME/Desktop/workspace"

if [ ! -d "$WORKSPACE_GOINFRE" ]; then
    echo "Created directory at $WORKSPACE_GOINFRE"
    mkdir -p "$WORKSPACE_GOINFRE"
fi

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
    local heavy_dirs=(".cache" ".npm" ".vscode" ".vscode-shared" ".copilot" ".dotnet")

    for dir in "${heavy_dirs[@]}"; do
        local target_home="$HOME/$dir"
        local target_goinfre="$REALOCATED/$dir"

        if [ -d "$target_home" ] && [ ! -L "$target_home" ]; then
            echo "Moving $dir to goinfre..."
            mv "$target_home" "$target_goinfre"
            ln -s "$target_goinfre" "$target_home"
            echo "Symlinked $dir -> $target_goinfre"
        fi
    done
}

logout() {
    if [ -d "$WORKSPACE_GOINFRE" ]; then
        for repo in "$WORKSPACE_GOINFRE"/*(/) ; do
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

    local heavy_dirs=(".cache" ".npm" ".vscode" ".vscode-shared" ".copilot" ".dotnet")
    for dir in "${heavy_dirs[@]}"; do
        if [ -L "$HOME/$dir" ]; then
            rm "$HOME/$dir"
        fi
    done

    rm -rf "$TOOLS"
    rm -rf "$CONFIG"
    rm -rf "$WORKSPACE_GOINFRE"
    rm -rf "/goinfre/$USER/realocated"
}
