"""Deterministic event contract validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from validator.parser import parse_track_events

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT / "event-contracts"
SAMPLE_DIR = ROOT / "sample-project"

CAMEL_TO_SNAKE = {
    "productId": "product_id",
    "productCategory": "product_category",
    "customerType": "customer_type",
    "planId": "plan_id",
    "planName": "plan_name",
    "cartId": "cart_id",
    "totalAmount": "total_amount",
}


def load_contracts_from_disk() -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    if not CONTRACTS_DIR.exists():
        return contracts
    for path in CONTRACTS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "event_name" not in data:
            continue
        contracts[data["event_name"]] = data
    return contracts


def contracts_from_db_rows(events: list[Any]) -> dict[str, dict[str, Any]]:
    """Build contract dict from SQLAlchemy Event rows."""
    contracts: dict[str, dict[str, Any]] = {}
    for event in events:
        params = {}
        for p in event.parameters:
            params[p.name] = {"type": p.type, "required": p.required}
        contracts[event.event_name] = {
            "event_name": event.event_name,
            "description": event.description,
            "version": event.version,
            "status": "APPROVED" if event.status == "ACTIVE" else event.status,
            "replacement": event.replacement,
            "platforms": [x for x in (event.platforms or "").split(",") if x],
            "aliases": [x for x in (getattr(event, "aliases", "") or "").split(",") if x],
            "parameters": params,
        }
    return contracts


def _similarity(a: str, b: str) -> float:
    a_set = set(a.lower().replace("_", " ").split())
    b_set = set(b.lower().replace("_", " ").split())
    # also compare compact forms
    ac = a.lower().replace("_", "")
    bc = b.lower().replace("_", "")
    if ac == bc:
        return 1.0
    if ac in bc or bc in ac:
        return 0.9
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def _contract_aliases(contract: dict[str, Any]) -> list[str]:
    raw = contract.get("aliases") or []
    if isinstance(raw, str):
        return [item for item in raw.split(",") if item]
    return list(raw)


def find_similar_event(name: str, contracts: dict[str, dict[str, Any]]) -> tuple[str | None, float]:
    compact = name.lower().replace("_", "")
    best_name = None
    best_score = 0.0
    for candidate, contract in contracts.items():
        if contract.get("status") == "DEPRECATED":
            continue
        for alias in _contract_aliases(contract):
            alias_compact = alias.lower().replace("_", "")
            if alias.lower() == name.lower() or alias_compact == compact:
                return candidate, 0.94
        score = _similarity(name, candidate)
        if score > best_score:
            best_score = score
            best_name = candidate
    if best_score >= 0.5:
        return best_name, round(best_score, 2)
    return None, 0.0


def suggested_implementation(contract: dict[str, Any]) -> str:
    params = contract.get("parameters") or {}
    lines = []
    for name, spec in params.items():
        typ = spec.get("type", "string") if isinstance(spec, dict) else "string"
        if typ == "number":
            rendered = "499"
        elif typ == "boolean":
            rendered = "true"
        else:
            rendered = f'"{name}"'
        lines.append(f"    {name}: {rendered},")
    body = "\n".join(lines)
    return f'trackEvent("{contract["event_name"]}", {{\n{body}\n}});'


def _approved(status: str | None) -> bool:
    return (status or "APPROVED").upper() in {"APPROVED", "ACTIVE"}


def validate_code(
    code: str,
    contracts: dict[str, dict[str, Any]],
    platform: str | None = None,
    filename: str | None = None,
    functions: list[str] | None = None,
    wrappers: list[dict[str, Any]] | None = None,
    changed_lines: set[int] | None = None,
) -> dict[str, Any]:
    events = parse_track_events(code, functions=functions, filename=filename, wrappers=wrappers)
    if changed_lines is not None:
        events = [event for event in events if event.get("line") in changed_lines]
        if not events:
            return {
                "status": "PASSED",
                "events_found": 0,
                "issues": [],
                "events": [],
                "suggested_implementation": None,
                "summary": "EVENT GOVERNANCE CHECK — PASSED. No tracking calls on changed lines.",
            }
    issues: list[dict[str, Any]] = []

    def add_issue(issue: dict[str, Any]) -> None:
        if filename:
            issue["file"] = filename
        issues.append(issue)

    if not events:
        add_issue(
            {
                "code": "NO_EVENTS",
                "severity": "warning",
                "event": None,
                "message": "No tracking calls found in the provided code.",
            }
        )

    for ev in events:
        name = ev["event_name"]
        if not name:
            add_issue(
                {
                    "code": "DYNAMIC_EVENT_NAME",
                    "severity": "error",
                    "event": None,
                    "line": ev.get("line"),
                    "message": "trackEvent name must be a string literal so governance can validate it.",
                }
            )
            continue
        contract = contracts.get(name)

        if contract is None:
            similar, score = find_similar_event(name, contracts)
            msg = f"Unknown event '{name}'."
            if similar:
                msg += f" Similar approved event exists: {similar} (similarity {int(score * 100)}%)."
            add_issue(
                {
                    "code": "UNKNOWN_EVENT",
                    "severity": "error",
                    "event": name,
                    "line": ev.get("line"),
                    "message": msg,
                    "expected": similar,
                    "actual": name,
                }
            )
            # still check naming on params against similar contract
            if similar:
                contract = contracts[similar]
            else:
                continue

        if not _approved(contract.get("status")) and contract.get("status") != "DEPRECATED":
            add_issue(
                {
                    "code": "NOT_APPROVED",
                    "severity": "error",
                    "event": name,
                    "line": ev.get("line"),
                    "message": f"Event '{name}' is {contract.get('status')} and cannot ship until approved.",
                    "expected": "APPROVED",
                    "actual": contract.get("status"),
                }
            )
            continue

        if contract.get("status") == "DEPRECATED":
            replacement = contract.get("replacement") or "an approved event"
            add_issue(
                {
                    "code": "DEPRECATED",
                    "severity": "error",
                    "event": name,
                    "line": ev.get("line"),
                    "message": f"Event '{name}' is DEPRECATED. Use '{replacement}' instead.",
                    "expected": replacement,
                    "actual": name,
                }
            )
            if contract.get("replacement") and contract["replacement"] in contracts:
                contract = contracts[contract["replacement"]]

        approved_platforms = contract.get("platforms") or []
        if platform and approved_platforms and platform.upper() not in [
            p.upper() for p in approved_platforms
        ]:
            add_issue(
                {
                    "code": "PLATFORM",
                    "severity": "error",
                    "event": contract["event_name"],
                    "line": ev.get("line"),
                    "message": (
                        f"Event '{contract['event_name']}' is not approved for platform {platform.upper()}. "
                        f"Approved: {', '.join(approved_platforms)}"
                    ),
                    "expected": ", ".join(approved_platforms),
                    "actual": platform.upper(),
                }
            )

        expected_params: dict[str, Any] = contract.get("parameters") or {}
        actual_params: dict[str, Any] = ev.get("parameters") or {}
        actual_types: dict[str, str] = ev.get("param_types") or {}

        # normalize camelCase keys
        normalized_actual = {}
        for key, value in actual_params.items():
            canon = CAMEL_TO_SNAKE.get(key, key)
            if key in CAMEL_TO_SNAKE and key != canon:
                add_issue(
                    {
                        "code": "PARAM_NAME",
                        "severity": "error",
                        "event": contract["event_name"],
                        "line": ev.get("line"),
                        "message": f"Parameter '{key}' should be '{canon}'.",
                        "expected": canon,
                        "actual": key,
                    }
                )
            normalized_actual[canon] = value
            if key in actual_types:
                actual_types[canon] = actual_types.get(canon, actual_types[key])

        for pname, spec in expected_params.items():
            required = spec.get("required", True) if isinstance(spec, dict) else True
            expected_type = spec.get("type", "string") if isinstance(spec, dict) else "string"
            if pname not in normalized_actual:
                if required:
                    add_issue(
                        {
                            "code": "MISSING_PARAM",
                            "severity": "error",
                            "event": contract["event_name"],
                            "line": ev.get("line"),
                            "message": f"Required parameter '{pname}' is missing.",
                            "expected": pname,
                            "actual": None,
                        }
                    )
                continue
            actual_type = actual_types.get(pname, "unknown")
            if expected_type == "number" and actual_type != "number":
                add_issue(
                    {
                        "code": "TYPE_MISMATCH",
                        "severity": "error",
                        "event": contract["event_name"],
                        "line": ev.get("line"),
                        "message": f"Parameter '{pname}' expected number, found {actual_type}.",
                        "expected": "number",
                        "actual": actual_type,
                    }
                )
            elif expected_type == "string" and actual_type != "string":
                add_issue(
                    {
                        "code": "TYPE_MISMATCH",
                        "severity": "error",
                        "event": contract["event_name"],
                        "line": ev.get("line"),
                        "message": f"Parameter '{pname}' expected string, found {actual_type}.",
                        "expected": "string",
                        "actual": actual_type,
                    }
                )
            elif expected_type == "boolean" and actual_type != "boolean":
                add_issue(
                    {
                        "code": "TYPE_MISMATCH",
                        "severity": "error",
                        "event": contract["event_name"],
                        "line": ev.get("line"),
                        "message": f"Parameter '{pname}' expected boolean, found {actual_type}.",
                        "expected": "boolean",
                        "actual": actual_type,
                    }
                )

    errors = [i for i in issues if i.get("severity") == "error"]
    status = "FAILED" if errors else "PASSED"

    suggestion = None
    if status == "FAILED":
        target_name = next(
            (
                issue.get("expected")
                for issue in issues
                if issue.get("expected") in contracts
            ),
            None,
        )
        if target_name is None:
            target_name = next(
                (issue.get("event") for issue in issues if issue.get("event") in contracts),
                None,
            )
        if target_name:
            suggestion = suggested_implementation(contracts[target_name])

    return {
        "status": status,
        "events_found": len(events),
        "issues": issues,
        "events": events,
        "suggested_implementation": suggestion,
        "summary": (
            f"EVENT GOVERNANCE CHECK — {status}. "
            f"Events found: {len(events)}. Issues: {len(errors)}."
        ),
    }


def load_sample_code(sample: str) -> str:
    if sample == "invalid":
        path = SAMPLE_DIR / "invalid" / "buyNow.js"
    elif sample == "valid":
        path = SAMPLE_DIR / "valid" / "buyNow.js"
    else:
        raise ValueError("sample must be 'valid' or 'invalid'")
    return path.read_text(encoding="utf-8")


def format_report(result: dict[str, Any]) -> str:
    lines = [
        "EVENT GOVERNANCE CHECK",
        "─" * 40,
        f"{'✓ PASSED' if result['status'] == 'PASSED' else '❌ FAILED'}",
        f"Events found: {result['events_found']}",
        "",
    ]
    if result["issues"]:
        lines.append("Issues:")
        for idx, issue in enumerate(result["issues"], 1):
            lines.append(f"  {idx}. [{issue['code']}] {issue['message']}")
        lines.append("")
    if result.get("suggested_implementation") and result["status"] == "FAILED":
        lines.append("Suggested implementation:")
        lines.append(result["suggested_implementation"])
        lines.append("")
    if result["status"] == "PASSED":
        lines.extend(
            [
                "✓ Event exists",
                "✓ Contract valid",
                "✓ Parameters valid",
                "✓ Types valid",
                "STATUS: PASS ✅",
            ]
        )
    return "\n".join(lines)
