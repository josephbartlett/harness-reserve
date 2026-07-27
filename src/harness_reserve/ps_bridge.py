from __future__ import annotations

import json
import sys


def bridge() -> int:
    if sys.version_info < (3, 11):
        print(
            "BLOCK: Harness Reserve requires Python 3.11 or later.",
            file=sys.stderr,
        )
        return 20
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeError) as exc:
        print(f"BLOCK: Invalid PowerShell argument bridge JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        print(
            "BLOCK: PowerShell argument bridge input must be a JSON array of strings.",
            file=sys.stderr,
        )
        return 2
    from .cli import main

    return main(value)


if __name__ == "__main__":
    raise SystemExit(bridge())
