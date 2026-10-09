"""Publish an approved contract as JSON Schema or a typed client."""

from __future__ import annotations

import json
import re
from typing import Any


def pascal(name: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Event"


def _spec(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        return spec
    return {"type": "string", "required": True, "allowed_values": [], "pii": False}


def json_schema(contract: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, raw in (contract.get("parameters") or {}).items():
        spec = _spec(raw)
        kind = spec.get("type") or "string"
        prop: dict[str, Any] = {"type": kind if kind in {"string", "number", "boolean"} else "string"}
        allowed = spec.get("allowed_values") or []
        if allowed:
            prop["enum"] = [_enum_value(kind, value) for value in allowed]
        if spec.get("pii"):
            prop["description"] = "Contains personal data"
        properties[name] = prop
        if spec.get("required", True):
            required.append(name)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": contract.get("event_name") or "event",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _enum_value(kind: str, value: str) -> Any:
    if kind == "number":
        return float(value) if "." in str(value) else int(value)
    if kind == "boolean":
        return str(value).lower() == "true"
    return str(value)


def _ts_field(name: str, spec: dict[str, Any]) -> str:
    kind = spec.get("type") or "string"
    allowed = spec.get("allowed_values") or []
    if allowed:
        rendered = " | ".join(json.dumps(_enum_value(kind, value)) for value in allowed)
    else:
        rendered = {"string": "string", "number": "number", "boolean": "boolean"}.get(kind, "string")
    optional = "" if spec.get("required", True) else "?"
    note = " // personal data" if spec.get("pii") else ""
    return f"  {name}{optional}: {rendered};{note}"


def typescript_source(contract: dict[str, Any]) -> str:
    fields = [_ts_field(name, _spec(spec)) for name, spec in (contract.get("parameters") or {}).items()]
    body = "\n".join(fields)
    return f"export interface {pascal(contract.get('event_name') or 'event')} {{\n{body}\n}}\n"


def _kotlin_type(spec: dict[str, Any]) -> str:
    kind = {"string": "String", "number": "Double", "boolean": "Boolean"}.get(spec.get("type") or "string", "String")
    if not spec.get("required", True):
        return f"{kind}?"
    return kind


def kotlin_source(contract: dict[str, Any]) -> str:
    lines = []
    for name, raw in (contract.get("parameters") or {}).items():
        spec = _spec(raw)
        note = " // personal data" if spec.get("pii") else ""
        allowed = spec.get("allowed_values") or []
        if allowed:
            note = f" // allowed: {', '.join(allowed)}{note}"
        lines.append(f"    val {name}: {_kotlin_type(spec)},{note}")
    body = "\n".join(lines)
    return f"data class {pascal(contract.get('event_name') or 'event')}(\n{body}\n)\n"


def _swift_type(spec: dict[str, Any]) -> str:
    kind = {"string": "String", "number": "Double", "boolean": "Bool"}.get(spec.get("type") or "string", "String")
    if not spec.get("required", True):
        return f"{kind}?"
    return kind


def swift_source(contract: dict[str, Any]) -> str:
    lines = []
    for name, raw in (contract.get("parameters") or {}).items():
        spec = _spec(raw)
        note = " // personal data" if spec.get("pii") else ""
        allowed = spec.get("allowed_values") or []
        if allowed:
            note = f" // allowed: {', '.join(allowed)}{note}"
        camel = name
        lines.append(f"    let {camel}: {_swift_type(spec)}{note}")
    body = "\n".join(lines)
    return f"struct {pascal(contract.get('event_name') or 'event')}: Codable {{\n{body}\n}}\n"


def render_type(contract: dict[str, Any], language: str) -> str:
    writers = {
        "typescript": typescript_source,
        "kotlin": kotlin_source,
        "swift": swift_source,
    }
    writer = writers.get(language)
    if writer is None:
        raise ValueError("language must be typescript, kotlin, or swift")
    return writer(contract)
