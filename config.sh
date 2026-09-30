#!/bin/zsh
#
# 42-config: the shell layer.
#
# This file only does what a subprocess cannot do for a shell: set this shell's
# environment and define its functions. Everything else lives in lib/, in Python,
# and is reached through the `42` command.
#
# This file contains no names, URLs or machine details. Personal settings live in
# ~/42.toml, which is not part of this repository. Run `42 --help` to start.

local script_path="${(%):-%x}"
local current_dir="$(cd -P "$(dirname "$script_path")" && pwd)"
local expected_dir="/goinfre/$USER/42-config"

if [ "$current_dir" != "$expected_dir" ]; then
    echo "42-config must live in $expected_dir, but it is in $current_dir"
    echo "  move it:   mv \"$current_dir\" \"$expected_dir\""
    echo "  or clone:  git clone <this repository> \"$expected_dir\""
    return 1
fi

CONFIG="$expected_dir"

# PATH and the tool variables. Only installed tools are added, so a missing one
# cannot poison PATH. See `42 env`.
eval "$(python3 "$CONFIG/lib/main.py" env)"

# One command for everything. `42 --help` lists the rest.
42() {
    case "$1" in
        update)
            # Re-reads this file, which only a sourced script can do.
            source "$CONFIG/config.sh"
            ;;
        install|space)
            # These can install tools that were missing when this shell started,
            # so pick up the new paths instead of making you open a new terminal.
            python3 "$CONFIG/lib/main.py" "$@"
            local status=$?
            eval "$(python3 "$CONFIG/lib/main.py" env)"
            rehash
            return $status
            ;;
        *)
            python3 "$CONFIG/lib/main.py" "$@"
            ;;
    esac
}

# Typed every session, and the one where fumbling costs data.
logout() { 42 logout }

rehash
