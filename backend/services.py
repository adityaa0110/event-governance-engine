from __future__ import annotations

import json

from models import Event, EventParameter
from schemas import EventContract, EventSummary, ParameterSpec
from sqlalchemy.orm import Session
from validator.engine import contracts_from_db_rows


def split_csv(value: str | None) -> list[str]:
    return [item for item in (value or "").split(",") if item]


def allowed_values(raw: str | None) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [item for item in text.split(",") if item]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item)]
    return []


def parameter_spec(parameter: EventParameter) -> ParameterSpec:
    return ParameterSpec(
        type=parameter.type,
        required=parameter.required,
        allowed_values=allowed_values(getattr(parameter, "allowed_values", "[]")),
        pii=bool(getattr(parameter, "pii", False)),
    )


def event_to_contract(event: Event) -> EventContract:
    params = {p.name: parameter_spec(p) for p in event.parameters}
    return EventContract(
        event_name=event.event_name,
        description=event.description,
        version=event.version,
        status="APPROVED" if event.status == "ACTIVE" else event.status,
        replacement=event.replacement,
        platforms=split_csv(event.platforms),
        aliases=split_csv(event.aliases),
        owner=event.owner or "",
        trigger=event.trigger or "",
        revision=event.revision or 1,
        parameters=params,
    )


def event_to_summary(event: Event) -> EventSummary:
    return EventSummary(
        event_name=event.event_name,
        description=event.description,
        version=event.version,
        status="APPROVED" if event.status == "ACTIVE" else event.status,
        platforms=split_csv(event.platforms),
        replacement=event.replacement,
        owner=event.owner or "",
        parameter_count=len(event.parameters),
    )


def get_contracts_map(db: Session) -> dict:
    events = db.query(Event).all()
    return contracts_from_db_rows(events)
