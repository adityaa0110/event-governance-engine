"""Seed catalogue from event-contracts/*.json"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from governance import normalize_status
from models import Event, EventParameter, TrackingFunction

CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "event-contracts"


def insert_contract_if_missing(db: Session, data: dict) -> bool:
    """JSON contracts are the initial seed. Later catalogue edits stay in the database."""
    if db.query(Event).filter(Event.event_name == data["event_name"]).first() is not None:
        return False
    platforms = data.get("platforms") or []
    platforms_str = ",".join(platforms) if isinstance(platforms, list) else str(platforms)
    aliases = data.get("aliases") or []
    aliases_str = ",".join(aliases) if isinstance(aliases, list) else str(aliases)
    event = Event(
        event_name=data["event_name"],
        description=data.get("description") or "",
        version=data.get("version") or "1.0",
        status=normalize_status(data.get("status") or "APPROVED"),
        replacement=data.get("replacement"),
        platforms=platforms_str,
        aliases=aliases_str,
        owner=data.get("owner") or "catalogue",
        trigger=data.get("trigger") or "",
    )
    for name, spec in (data.get("parameters") or {}).items():
        event.parameters.append(
            EventParameter(
                name=name,
                type=(spec or {}).get("type", "string"),
                required=bool((spec or {}).get("required", True)),
            )
        )
    db.add(event)
    return True


def seed_tracking_functions(db: Session) -> None:
    path = CONTRACTS_DIR / "tracking.json"
    specs = [{"name": "trackEvent", "style": "auto", "event_arg": 0, "params_arg": 1}]
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        names = loaded.get("functions") or []
        specs = [
            {"name": name, "style": "auto", "event_arg": 0, "params_arg": 1}
            for name in names
        ] or specs
        for wrapper in loaded.get("wrappers") or []:
            if wrapper.get("name"):
                specs.append(wrapper)
    existing = {row.name: row for row in db.query(TrackingFunction).all()}
    for spec in specs:
        name = spec["name"]
        if name in existing:
            continue
        db.add(
            TrackingFunction(
                name=name,
                style=spec.get("style") or "auto",
                event_arg=int(spec.get("event_arg", 0)),
                params_arg=int(spec.get("params_arg", 1)),
            )
        )


def seed_database(db: Session) -> int:
    count = 0
    if CONTRACTS_DIR.exists():
        for path in sorted(CONTRACTS_DIR.glob("*.json")):
            if path.name == "tracking.json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if "event_name" not in data:
                continue
            if insert_contract_if_missing(db, data):
                count += 1
    seed_tracking_functions(db)
    db.commit()
    return count
