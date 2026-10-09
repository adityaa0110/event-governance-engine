from __future__ import annotations

from models import Event
from schemas import EventContract, EventSummary, ParameterSpec
from sqlalchemy.orm import Session
from validator.engine import contracts_from_db_rows


def split_csv(value: str | None) -> list[str]:
    return [item for item in (value or "").split(",") if item]


def event_to_contract(event: Event) -> EventContract:
    params = {
        p.name: ParameterSpec(type=p.type, required=p.required) for p in event.parameters
    }
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
