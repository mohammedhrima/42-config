"""Writing VS Code's settings.json.

settings.json is JSONC: it allows comments and trailing commas. Parsing it with a
JSON library and writing it back would silently delete every comment the user
wrote, so it is edited as text, one line at a time.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import log

SETTINGS_FILE = Path.home() / ".config" / "Code" / "User" / "settings.json"


def _replace_line(lines: list[str], key: str, value: str) -> bool:
    """Rewrite the value of `key` in place. Returns True if the file changed.

    Commented-out lines are skipped, so a `// "workbench.colorTheme": ...` left
    in the file is not mistaken for the real setting.
    """
    pattern = re.compile(r'^(\s*)"' + re.escape(key) + r'"(\s*:\s*)"[^"]*"(.*)$')

    for index, line in enumerate(lines):
        if line.lstrip().startswith("//"):
            continue
        match = pattern.match(line)
        if not match:
            continue
        indent, separator, trailing = match.groups()
        rewritten = f'{indent}"{key}"{separator}{json.dumps(value)}{trailing}\n'
        if rewritten == line:
            log.info(f"{key} already {value}")
            return False
        lines[index] = rewritten
        log.ok(f"{key} = {value}")
        return True

    return _insert_line(lines, key, value)


def _insert_line(lines: list[str], key: str, value: str) -> bool:
    """Add a key that is not in the file yet, just after the opening brace."""
    for index, line in enumerate(lines):
        if "{" in line:
            lines.insert(index + 1, f'  "{key}": {json.dumps(value)},\n')
            log.ok(f"{key} = {value} (added)")
            return True
    log.err(f"{SETTINGS_FILE} has no opening brace, leaving it alone")
    return False


def apply_settings(settings: dict[str, str], path: Path = SETTINGS_FILE) -> int:
    """Set each key in VS Code's settings.json, keeping the rest of the file."""
    if not settings:
        return 0

    log.step("Applying VS Code settings")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{\n}\n")

    lines = path.read_text().splitlines(keepends=True)
    changed = False
    for key, value in settings.items():
        if _replace_line(lines, key, str(value)):
            changed = True

    if changed:
        path.write_text("".join(lines))
    return 0
