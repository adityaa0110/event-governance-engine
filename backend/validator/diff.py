"""Changed-line ranges from a unified git diff."""

from __future__ import annotations

import re

_FILE = re.compile(r"^\+\+\+ b/(.+)$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_unified_diff(diff: str) -> dict[str, set[int]]:
    current: str | None = None
    lines: dict[str, set[int]] = {}
    for raw in diff.splitlines():
        file_match = _FILE.match(raw)
        if file_match:
            path = file_match.group(1)
            current = None if path == "/dev/null" else path
            if current is not None:
                lines.setdefault(current, set())
            continue
        if current is None:
            continue
        hunk = _HUNK.match(raw)
        if not hunk:
            continue
        start = int(hunk.group(1))
        count = int(hunk.group(2) if hunk.group(2) is not None else 1)
        lines[current].update(range(start, start + count))
    return lines
