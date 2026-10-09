"""Extract tracking calls from JS/TS, Kotlin, Swift, and Java source."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

PARSER_SCRIPT = Path(__file__).resolve().parents[2] / "validator-cli" / "parse_events.mjs"


TRACK_EVENT_RE = re.compile(
    r"""trackEvent\s*\(\s*['"]([^'"]+)['"]\s*,\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*\)""",
    re.MULTILINE,
)

PROP_RE = re.compile(
    r"""(['"]?)([A-Za-z_][A-Za-z0-9_]*)\1\s*:\s*("""
    r"""'(?:\\'|[^'])*'|"(?:\\"|[^"])*"|`(?:\\`|[^`])*`|"""
    r"""-?\d+(?:\.\d+)?|true|false|null|[A-Za-z_][A-Za-z0-9_.]*)""",
    re.MULTILINE,
)


def _infer_type(raw: str) -> tuple[Any, str]:
    value = raw.strip()
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ) or (value.startswith("`") and value.endswith("`")):
        return value[1:-1], "string"
    if value in ("true", "false"):
        return value == "true", "boolean"
    if value == "null":
        return None, "null"
    try:
        if "." in value:
            return float(value), "number"
        return int(value), "number"
    except ValueError:
        return value, "unknown"


def default_tracking_functions() -> list[str]:
    path = PARSER_SCRIPT.parents[1] / "event-contracts" / "tracking.json"
    try:
        names = json.loads(path.read_text(encoding="utf-8")).get("functions") or []
    except (OSError, json.JSONDecodeError):
        names = []
    cleaned = [name for name in names if isinstance(name, str) and name.strip()]
    return cleaned or ["trackEvent"]


def parse_with_babel(code: str, functions: list[str] | None = None) -> list[dict[str, Any]] | None:
    if not PARSER_SCRIPT.exists() or not (PARSER_SCRIPT.parent / "node_modules").exists():
        return None
    env = os.environ.copy()
    env["TRACKING_FUNCTIONS"] = ",".join(functions or default_tracking_functions())
    try:
        completed = subprocess.run(
            ["node", str(PARSER_SCRIPT)],
            input=code,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def parse_with_regex(code: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for match in TRACK_EVENT_RE.finditer(code):
        event_name = match.group(1)
        body = match.group(2)
        line = code[: match.start()].count("\n") + 1
        parameters: dict[str, Any] = {}
        param_types: dict[str, str] = {}
        for prop in PROP_RE.finditer(body):
            key = prop.group(2)
            raw_val = prop.group(3)
            value, typ = _infer_type(raw_val)
            parameters[key] = value
            param_types[key] = typ
        found.append(
            {
                "event_name": event_name,
                "parameters": parameters,
                "param_types": param_types,
                "line": line,
                "dynamic": False,
            }
        )
    return found


_VALUE = (
    r"""'(?:\\'|[^'])*'|"(?:\\"|[^"])*"|`(?:\\`|[^`])*`|-?\d+(?:\.\d+)?|true|false|null"""
)
_NAMED_PAIR = re.compile(
    rf"""['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*(?:to|:)\s*({_VALUE})"""
)
_COMMA_PAIR = re.compile(
    rf"""['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*,\s*({_VALUE})"""
)
_JS_SUFFIXES = {"", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def _read_call_body(code: str, start: int) -> str:
    index = start
    while index < len(code) and code[index] in " \t\r\n":
        index += 1
    if index >= len(code) or code[index] != ",":
        return ""
    index += 1
    depth = 1
    begin = index
    while index < len(code):
        char = code[index]
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
            if depth == 0:
                return code[begin:index]
        index += 1
    return code[begin:]


def _pairs(body: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for pattern in (_NAMED_PAIR, _COMMA_PAIR):
        for match in pattern.finditer(body):
            found.setdefault(match.group(1), match.group(2))
    return found


def parse_configured_calls(code: str, functions: list[str] | None = None) -> list[dict[str, Any]]:
    names = functions or default_tracking_functions()
    leaves = [name.split(".")[-1] for name in names if name.split(".")[-1]]
    if not leaves:
        return []
    pattern = re.compile(
        rf"(?<![\w.])(?:{'|'.join(re.escape(name) for name in leaves)})\s*\(\s*['\"]([^'\"]+)['\"]"
    )
    found: list[dict[str, Any]] = []
    for match in pattern.finditer(code):
        body = _read_call_body(code, match.end())
        parameters: dict[str, Any] = {}
        param_types: dict[str, str] = {}
        dynamic = False
        for key, raw in _pairs(body).items():
            value, typ = _infer_type(raw)
            parameters[key] = value
            param_types[key] = typ
            if typ == "unknown":
                dynamic = True
        found.append(
            {
                "event_name": match.group(1),
                "parameters": parameters,
                "param_types": param_types,
                "line": code[: match.start()].count("\n") + 1,
                "dynamic": dynamic,
            }
        )
    return found


def load_wrappers() -> list[dict[str, Any]]:
    path = PARSER_SCRIPT.parents[1] / "event-contracts" / "tracking.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    from validator.languages import normalize_wrappers

    return normalize_wrappers(data.get("functions") or ["trackEvent"], data.get("wrappers") or [])


def parse_track_events(
    code: str,
    functions: list[str] | None = None,
    filename: str | None = None,
    wrappers: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    from validator.languages import normalize_wrappers, parse_language_calls

    names = functions or default_tracking_functions()
    configured = normalize_wrappers(names, wrappers if wrappers is not None else load_wrappers())
    suffix = Path(filename).suffix.lower() if filename else ""
    if suffix in _JS_SUFFIXES:
        parsed = parse_with_babel(code, [item["name"] for item in configured])
        if parsed:
            return parsed
    language_calls = parse_language_calls(code, configured)
    if language_calls:
        return language_calls
    configured_calls = parse_configured_calls(code, [item["name"] for item in configured])
    if configured_calls:
        return configured_calls
    if suffix in _JS_SUFFIXES:
        return parse_with_regex(code)
    return []
