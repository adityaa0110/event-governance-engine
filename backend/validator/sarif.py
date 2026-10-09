"""SARIF 2.1.0 output for tracking-call findings."""

from __future__ import annotations

import json
from pathlib import Path


def sarif_document(findings: list[dict]) -> dict:
    results = []
    for finding in findings:
        result = {
            "ruleId": finding.get("code") or "governance",
            "level": "error" if finding.get("severity") == "error" else "warning",
            "message": {"text": finding.get("message") or ""},
        }
        path = finding.get("file")
        if path:
            location = {
                "physicalLocation": {
                    "artifactLocation": {"uri": Path(path).as_posix()},
                    "region": {"startLine": finding.get("line") or 1},
                }
            }
            result["locations"] = [location]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "event-governance", "version": "1.2.0"}},
                "results": results,
            }
        ],
    }


def write_sarif(path: Path, findings: list[dict]) -> None:
    path.write_text(json.dumps(sarif_document(findings), indent=2), encoding="utf-8")


def comment_markdown(findings: list[dict]) -> str:
    if not findings:
        return "Event governance found no tracking issues on the changed lines."
    lines = ["Event governance failed on tracking calls in the changed lines.", ""]
    for finding in findings:
        location = finding.get("file") or "code"
        if finding.get("line"):
            location = f"{location}:{finding['line']}"
        lines.append(f"- `{finding.get('code')}` {location}: {finding.get('message')}")
    return "\n".join(lines) + "\n"
