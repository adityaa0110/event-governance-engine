"""Contract workflow, version history, and immutable audit records."""

from __future__ import annotations

import json
import re

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth import Principal
from config import audit_retention_days
from models import AuditLog, Event, EventParameter, EventVersion, utcnow
from tracing import current_trace_id
from schemas import ParameterSpec
from services import event_to_contract

EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PARAM_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ALLOWED_TYPES = {"string", "number", "boolean"}
APPROVED_STATUSES = {"APPROVED", "ACTIVE"}


def normalize_status(status: str | None) -> str:
    value = (status or "DRAFT").upper()
    return "APPROVED" if value == "ACTIVE" else value


def snapshot(event: Event) -> dict:
    return event_to_contract(event).model_dump()


def record_audit(
    db: Session,
    principal: Principal,
    action: str,
    entity_id: str,
    before: dict | None,
    after: dict | None,
    comment: str = "",
) -> None:
    db.add(
        AuditLog(
            actor=principal.email or principal.subject,
            action=action,
            entity_type="event",
            entity_id=entity_id,
            before_json=json.dumps(before or {}),
            after_json=json.dumps(after or {}),
            comment=comment,
            trace_id=current_trace_id(),
        )
    )


def record_version(
    db: Session, event: Event, principal: Principal, action: str, comment: str = ""
) -> None:
    db.add(
        EventVersion(
            event_name=event.event_name,
            version=event.version,
            status=normalize_status(event.status),
            action=action,
            actor=principal.email or principal.subject,
            comment=comment,
            snapshot_json=json.dumps(snapshot(event)),
        )
    )


def contract_diff(current: dict, approved: dict | None) -> list[dict]:
    if not approved:
        return []
    changes = []
    for field in ("description", "version", "status", "trigger", "platforms", "aliases", "parameters", "replacement"):
        before = approved.get(field)
        after = current.get(field)
        if before != after:
            changes.append({"field": field, "before": before, "after": after})
    return changes


def validate_contract_shape(event_name: str, parameters: dict[str, ParameterSpec]) -> None:
    if not EVENT_NAME_RE.match(event_name):
        raise HTTPException(status_code=422, detail="Event names must be snake_case")
    seen = set()
    for name, spec in parameters.items():
        if not PARAM_NAME_RE.match(name):
            raise HTTPException(status_code=422, detail=f"Parameter '{name}' must be snake_case")
        if name in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate parameter '{name}'")
        seen.add(name)
        if spec.type not in ALLOWED_TYPES:
            raise HTTPException(status_code=422, detail=f"Unsupported type '{spec.type}'")


def replace_parameters(event: Event, parameters: dict[str, ParameterSpec]) -> None:
    event.parameters.clear()
    for name, spec in parameters.items():
        event.parameters.append(EventParameter(name=name, type=spec.type, required=spec.required))


def last_approved_snapshot(db: Session, event_name: str) -> dict | None:
    rows = (
        db.query(EventVersion)
        .filter(EventVersion.event_name == event_name, EventVersion.action == "approve")
        .order_by(EventVersion.id.desc())
        .all()
    )
    if not rows:
        return None
    return json.loads(rows[0].snapshot_json or "{}")


def is_breaking(previous: dict, updated: dict) -> bool:
    old_params = previous.get("parameters") or {}
    new_params = updated.get("parameters") or {}
    for name, spec in old_params.items():
        if name not in new_params:
            return True
        old_type = spec.get("type") if isinstance(spec, dict) else spec
        new_type = new_params[name].get("type") if isinstance(new_params[name], dict) else new_params[name]
        if old_type != new_type:
            return True
        old_required = spec.get("required", True) if isinstance(spec, dict) else True
        new_required = new_params[name].get("required", True) if isinstance(new_params[name], dict) else True
        if new_required and not old_required:
            return True
    return False


def require_revision(event: Event, expected: int | None) -> None:
    current = event.revision or 1
    if expected is not None and expected != current:
        raise HTTPException(
            status_code=409,
            detail=f"Contract changed since it was loaded (revision {current})",
        )
    event.revision = current + 1


def prune_audit(db: Session) -> int:
    days = audit_retention_days()
    if days <= 0:
        return 0
    cutoff = utcnow() - timedelta(days=days)
    return db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete()


def major_version(value: str) -> int:
    try:
        return int(str(value).split(".", 1)[0])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Version must start with a number") from exc


def bump_minor(version: str) -> str:
    parts = str(version).split(".")
    major = major_version(version)
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return f"{major}.{minor + 1}"


def transition(
    db: Session,
    event: Event,
    action: str,
    principal: Principal,
    replacement: str | None = None,
    comment: str | None = None,
    expected_revision: int | None = None,
) -> Event:
    require_revision(event, expected_revision)
    before = snapshot(event)
    status = normalize_status(event.status)
    event.status = status

    if action == "submit":
        if not principal.has("editor"):
            raise HTTPException(status_code=403, detail="editor role required")
        if status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft contracts can be submitted")
        event.status = "REVIEW"
    elif action == "approve":
        if not principal.has("approver"):
            raise HTTPException(status_code=403, detail="approver role required")
        if status != "REVIEW":
            raise HTTPException(status_code=409, detail="Only contracts in review can be approved")
        approved = last_approved_snapshot(db, event.event_name)
        current = snapshot(event)
        if approved and is_breaking(approved, current) and major_version(event.version) <= major_version(approved.get("version", "0")):
            raise HTTPException(status_code=409, detail="Breaking change requires a major version bump")
        event.status = "APPROVED"
    elif action == "reject":
        if not principal.has("approver"):
            raise HTTPException(status_code=403, detail="approver role required")
        if status != "REVIEW":
            raise HTTPException(status_code=409, detail="Only contracts in review can be rejected")
        if not (comment or "").strip():
            raise HTTPException(status_code=422, detail="Rejection requires a comment")
        event.status = "DRAFT"
    elif action == "revise":
        if not principal.has("editor"):
            raise HTTPException(status_code=403, detail="editor role required")
        if status != "APPROVED":
            raise HTTPException(status_code=409, detail="Only approved contracts can be revised")
        record_version(db, event, principal, "revise-from")
        event.status = "DRAFT"
        event.version = bump_minor(event.version)
    elif action == "deprecate":
        if not principal.has("approver"):
            raise HTTPException(status_code=403, detail="approver role required")
        if status != "APPROVED":
            raise HTTPException(status_code=409, detail="Only approved contracts can be deprecated")
        if not replacement:
            raise HTTPException(status_code=422, detail="Deprecation requires a replacement event")
        if replacement == event.event_name:
            raise HTTPException(status_code=422, detail="Replacement must be a different event")
        target = db.query(Event).filter(Event.event_name == replacement).first()
        if target is None or normalize_status(target.status) not in APPROVED_STATUSES:
            raise HTTPException(status_code=422, detail="Replacement must be an approved event")
        event.status = "DEPRECATED"
        event.replacement = replacement
    else:
        raise HTTPException(status_code=400, detail="Unknown workflow action")

    note = (comment or "").strip() if action == "reject" else ""
    record_version(db, event, principal, action, note)
    record_audit(db, principal, action, event.event_name, before, snapshot(event), note)
    return event
