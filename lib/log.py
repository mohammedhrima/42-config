"""Terminal output for 42-config.

Deliberately matches the old shell helpers (_step/_info/_ok/_err) so switching a
command from zsh to Python does not change what the user sees.
"""

import sys


def step(message: str) -> None:
    """A heading for a new phase of work."""
    print(f"\n==> {message}")


def info(message: str) -> None:
    """Detail under the current heading."""
    print(f"    {message}")


def ok(message: str) -> None:
    """Something finished successfully."""
    print(f"    [ok] {message}")


def err(message: str) -> None:
    """Something failed. Goes to stderr so it survives redirection."""
    print(f"    [!!] {message}", file=sys.stderr)
