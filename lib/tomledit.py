"""Small, targeted edits to ~/42.toml.

tomllib can read TOML but not write it, and rewriting the file from parsed data
would delete every comment in it. So edits are done on the text: a table's body is
replaced in place, and a new array-of-tables entry is appended. Nothing else in the
file is touched.
"""

from __future__ import annotations

from pathlib import Path


def set_table(path: Path, table: str, entries: dict[str, str]) -> None:
    """Replace the body of ``[table]`` with `entries`, keeping the rest of the file.

    The table is created at the end if it does not exist yet.
    """
    lines = path.read_text().splitlines() if path.exists() else []
    header = f"[{table}]"

    body = [f'{key} = "{value}"' for key, value in sorted(entries.items())]

    if header not in lines:
        block = ([""] if lines and lines[-1] != "" else []) + [header] + body
        path.write_text("\n".join(lines + block) + "\n")
        return

    start = lines.index(header)
    end = start + 1
    # The table ends at the next header, and comments before it belong to it.
    while end < len(lines) and not lines[end].lstrip().startswith("["):
        end += 1

    kept_comments = [line for line in lines[start + 1:end] if line.lstrip().startswith("#")]
    rebuilt = lines[:start + 1] + kept_comments + body + [""] + lines[end:]
    path.write_text("\n".join(rebuilt).rstrip("\n") + "\n")


def append_entry(path: Path, table: str, entry: dict[str, object]) -> None:
    """Append one ``[[table]]`` entry to the end of the file."""
    lines = [f"", f"[[{table}]]"]
    for key, value in entry.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        else:
            lines.append(f'{key} = "{value}"')

    existing = path.read_text() if path.exists() else ""
    path.write_text(existing.rstrip("\n") + "\n" + "\n".join(lines) + "\n")
