#!/usr/bin/env python
"""CI gate against new raw ORM queries outside the repository layer.

Tenant isolation (business_id filtering) is enforced by convention in
app/repositories/*.py, not by the database - see BaseRepository. Code that
calls .query()/.execute(select(...)) directly, bypassing a repository, carries
that isolation burden itself, and a missed filter there is a cross-tenant data
leak with no safety net underneath it.

A blanket ban would false-positive on the many services that legitimately
query a secondary/related model directly (e.g. sales_order.py querying
StockLevel) - rewriting all of that into repositories is a much bigger
project than this gate. Instead this is a ratchet: every raw query line
present today is frozen into scripts/raw_query_baseline.json. CI fails only
if a *new* raw query line (not in the baseline) shows up outside
app/repositories/ - so new code is held to the repository pattern, without
forcing an unscoped rewrite of what already exists.

Usage:
    python scripts/check_raw_queries.py            # check for new violations
    python scripts/check_raw_queries.py --write     # (re)write the baseline
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = REPO_ROOT / "app"
BASELINE_PATH = Path(__file__).resolve().parent / "raw_query_baseline.json"

# Matches SQLAlchemy's legacy Query API (the pattern this codebase uses
# throughout) - db.query(...), session.query(...), self.db.query(...).
RAW_QUERY_PATTERN = re.compile(r"\.query\(")

EXCLUDED_DIRS = {"repositories", "__pycache__"}


def find_raw_query_lines(root: Path) -> dict[str, list[str]]:
    """Return {relative_file_path: [stripped_line, ...]} for every line
    outside app/repositories/ that calls the raw Query API."""
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        rel_path = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        lines = path.read_text(encoding="utf-8").splitlines()
        matches = [line.strip() for line in lines if RAW_QUERY_PATTERN.search(line)]
        if matches:
            found[rel_path] = matches
    return found


def load_baseline() -> dict[str, list[str]]:
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def write_baseline(current: dict[str, list[str]]) -> None:
    BASELINE_PATH.write_text(
        json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote baseline with {sum(len(v) for v in current.values())} "
          f"known raw-query lines across {len(current)} files to {BASELINE_PATH}")


def main() -> int:
    current = find_raw_query_lines(APP_ROOT)

    if "--write" in sys.argv:
        write_baseline(current)
        return 0

    baseline = load_baseline()
    violations: dict[str, list[str]] = {}

    for file, lines in current.items():
        allowed = baseline.get(file, [])
        # Compare as multisets so a line already known for this file doesn't
        # get flagged again, but an extra copy or a genuinely new line does.
        allowed_remaining = list(allowed)
        new_lines = []
        for line in lines:
            if line in allowed_remaining:
                allowed_remaining.remove(line)
            else:
                new_lines.append(line)
        if new_lines:
            violations[file] = new_lines

    if violations:
        print("New raw ORM query calls found outside app/repositories/:\n")
        for file, lines in violations.items():
            print(f"  {file}")
            for line in lines:
                print(f"    + {line}")
            print()
        print(
            "Route these through a repository method instead (see "
            "app/repositories/base.py), so tenant filtering is enforced in "
            "one reviewed place. If this raw query is genuinely necessary, "
            "run `python scripts/check_raw_queries.py --write` after review "
            "to accept it into the baseline."
        )
        return 1

    print(f"OK - no new raw queries outside app/repositories/ "
          f"({sum(len(v) for v in current.values())} baselined lines unchanged).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
