#!/bin/zsh

CONFIG="/goinfre/$USER/42-config"
TOOLS="/goinfre/$USER/tools"

mkdir -p $TOOLS

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


echo "Hello $USER"