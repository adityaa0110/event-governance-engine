#!/usr/bin/env python3
"""CLI: event-validator scan <path>"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from validator.diff import parse_unified_diff  # noqa: E402
from validator.sarif import comment_markdown, write_sarif  # noqa: E402
from validator.engine import (  # noqa: E402
    format_report,
    load_contracts_from_disk,
    validate_code,
)

SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".kt", ".kts", ".swift", ".java"}


def collect_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in SOURCE_SUFFIXES else []
    files: list[Path] = []
    for pattern in (
        "**/*.js",
        "**/*.jsx",
        "**/*.ts",
        "**/*.tsx",
        "**/*.kt",
        "**/*.kts",
        "**/*.swift",
        "**/*.java",
    ):
        files.extend(path.glob(pattern))
    return sorted(files)


def changed_files(base: str) -> dict[Path, set[int]]:
    import subprocess

    completed = subprocess.run(
        ["git", "diff", "-U0", "--no-color", base, "--"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git diff failed")
    mapped: dict[Path, set[int]] = {}
    for relative, lines in parse_unified_diff(completed.stdout).items():
        path = (ROOT / relative).resolve()
        if path.suffix.lower() in SOURCE_SUFFIXES and path.is_file():
            mapped[path] = lines
    return mapped


def scan(
    path: Path | None = None,
    changed: bool = False,
    base: str = "origin/main",
    output: Path | None = None,
    comment_file: Path | None = None,
) -> int:
    contracts = load_contracts_from_disk()
    if not contracts:
        print("No contracts found in event-contracts/", file=sys.stderr)
        return 2

    line_map: dict[Path, set[int]] | None = None
    if changed:
        try:
            line_map = changed_files(base)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        files = sorted(line_map)
        if path is not None:
            target = path.resolve()
            files = [item for item in files if item == target or target in item.parents]
        if not files:
            print("No changed source files to validate")
            if output is not None:
                write_sarif(output, [])
            if comment_file is not None:
                comment_file.write_text(comment_markdown([]), encoding="utf-8")
            return 0
    else:
        if path is None:
            print("scan requires a path or --changed", file=sys.stderr)
            return 2
        files = collect_files(path)
        if not files:
            print(f"No source files under {path}")
            return 2

    overall_failed = False
    total_events = 0
    total_issues = 0
    findings: list[dict] = []

    print("EVENT GOVERNANCE CHECK")
    print("─" * 40)
    print(f"Scanning: {path or base}")
    print(f"Contracts loaded: {len(contracts)}")
    print()

    for file in files:
        code = file.read_text(encoding="utf-8")
        result = validate_code(
            code,
            contracts,
            filename=str(file),
            changed_lines=None if line_map is None else line_map.get(file, set()),
        )
        total_events += result["events_found"]
        errors = [i for i in result["issues"] if i.get("severity") == "error"]
        total_issues += len(errors)
        status_icon = "✓" if result["status"] == "PASSED" else "❌"
        label = file.relative_to(ROOT) if file.is_relative_to(ROOT) else file.name
        print(f"{status_icon} {label} — {result['status']}")
        if result["events_found"] == 0 and not errors:
            print("  (no tracking calls on changed lines)" if changed else "  (no tracking calls)")
        for issue in result["issues"]:
            location = f" line {issue['line']}" if issue.get("line") else ""
            print(f"  - [{issue['code']}]{location} {issue['message']}")
            finding = {**issue, "file": str(label)}
            findings.append(finding)
            if os.getenv("GITHUB_ACTIONS") == "true" and issue.get("severity") == "error":
                line_no = issue.get("line") or 1
                message = (issue.get("message") or "").replace("\n", " ")
                print(f"::error file={label},line={line_no}::{message}")
        if result["status"] == "FAILED":
            overall_failed = True
            if result.get("suggested_implementation"):
                print("  Suggested:")
                for line in result["suggested_implementation"].splitlines():
                    print(f"    {line}")
        print()

    print("─" * 40)
    print(f"Events found: {total_events}")
    print(f"Issues: {total_issues}")
    print("STATUS: FAIL ❌" if overall_failed else "STATUS: PASS ✅")
    errors = [item for item in findings if item.get("severity") == "error"]
    if output is not None:
        write_sarif(output, errors)
    if comment_file is not None:
        comment_file.write_text(comment_markdown(errors), encoding="utf-8")
    return 1 if overall_failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="event-validator", description="Validate analytics trackEvent usage")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_p = sub.add_parser("scan", help="Scan a file or directory")
    scan_p.add_argument("path", nargs="?", type=Path, help="File or directory to scan")
    scan_p.add_argument("--changed", action="store_true", help="Validate tracking calls on lines changed from --base")
    scan_p.add_argument("--base", default="origin/main", help="Git ref used with --changed")
    scan_p.add_argument("--output", type=Path, help="Write a SARIF report")
    scan_p.add_argument("--comment-file", type=Path, help="Write a pull-request comment body")
    args = parser.parse_args(argv)
    if args.command == "scan":
        return scan(
            args.path,
            changed=args.changed,
            base=args.base,
            output=args.output,
            comment_file=args.comment_file,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
