from __future__ import annotations

import hashlib
import json
import re

from ai.event_analyzer import generate_events
from auth import Principal, get_current_user, require_role
from config import auth_disabled, oidc_audience, oidc_client_id, oidc_issuer, oidc_scopes
from database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from governance import (
    contract_diff,
    last_approved_snapshot,
    record_audit,
    record_version,
    replace_parameters,
    require_revision,
    snapshot,
    transition,
    validate_contract_shape,
)
from models import (
    AiRun,
    AuditLog,
    Event,
    EventUsage,
    EventVersion,
    Notification,
    RecommendationDecision,
    TrackingFunction,
    ValidationResult,
)
from publish import json_schema, render_type
from schemas import (
    AiRunOut,
    AuditEntry,
    AuditPage,
    ContractDiff,
    DashboardStats,
    DiffChange,
    EventContract,
    EventCreate,
    EventPage,
    EventSummary,
    EventUpdate,
    EventVersionOut,
    FoundEvent,
    GenerateRequest,
    GenerateResponse,
    JsonSchemaOut,
    NotificationOut,
    PayloadCheckRequest,
    PrincipalOut,
    PublicConfig,
    PublishedType,
    QueueItem,
    RecommendationDecisionOut,
    RecommendationPage,
    RecommendationRequest,
    TrackingFunctionIn,
    TransitionRequest,
    UsageSummary,
    ValidateCodeRequest,
    ValidateResponse,
    ValidationIssue,
    ValidationResultOut,
)
from services import event_to_contract, event_to_summary, get_contracts_map
from observability import notify_alert, record_ai_failure, record_validation
from tracing import current_trace_id
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload
from validator.engine import format_report, load_sample_code, validate_code, validate_payload

public_router = APIRouter()
router = APIRouter()
FUNCTION_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

DEMO_PRD = (
    "Feature: Buy Now for Broadband Plans\n"
    "As a customer, I can select a broadband plan and click Buy Now.\n"
    "After clicking Buy Now, I proceed to checkout to complete purchase.\n"
    "Track plan selection, buy click, and checkout start for analytics.\n"
    "Platform: BROADBAND (also used on APP and SHOP)."
)


def _event_query(db: Session):
    return db.query(Event).options(selectinload(Event.parameters))


def _record_usages(db: Session, events: list[dict], repository: str, validation_id: int | None, principal: Principal) -> None:
    actor = principal.email or principal.subject
    seen: set[str] = set()
    for event in events:
        name = event.get("event_name")
        if not name or name in seen:
            continue
        seen.add(name)
        db.add(
            EventUsage(
                event_name=name,
                repository=repository,
                file=event.get("file") or "",
                line=event.get("line"),
                validation_id=validation_id,
                actor=actor,
            )
        )


def _audiences(principal: Principal) -> set[str]:
    audiences = {principal.email or "", principal.subject}
    if principal.has("approver"):
        audiences.add("approver")
    if principal.has("editor"):
        audiences.add("editor")
    return {item for item in audiences if item}


def _notification_out(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        audience=row.audience,
        event_name=row.event_name,
        kind=row.kind,
        message=row.message,
        read=bool(row.read),
        created_at=row.created_at,
    )


def _get_event(db: Session, event_name: str) -> Event:
    event = _event_query(db).filter(Event.event_name == event_name).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@public_router.get("/health")
def health():
    return {"status": "ok", "service": "event-governance-engine"}


@public_router.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@public_router.get("/config", response_model=PublicConfig)
def public_config():
    return PublicConfig(
        auth_required=not auth_disabled(),
        issuer=oidc_issuer(),
        client_id=oidc_client_id(),
        audience=oidc_audience(),
        scopes=oidc_scopes(),
    )


@public_router.get("/demo/prd")
def demo_prd():
    return {"requirement": DEMO_PRD, "platform": "BROADBAND"}


@router.get("/me", response_model=PrincipalOut)
def me(principal: Principal = Depends(get_current_user)):
    return PrincipalOut(
        subject=principal.subject,
        email=principal.email,
        name=principal.name,
        roles=sorted(principal.roles),
    )


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    approved = sum(1 for event in events if event.status in {"APPROVED", "ACTIVE"})
    draft = sum(1 for event in events if event.status == "DRAFT")
    in_review = sum(1 for event in events if event.status == "REVIEW")
    deprecated = sum(1 for event in events if event.status == "DEPRECATED")
    validations = db.query(ValidationResult).order_by(ValidationResult.id.desc()).limit(50).all()
    last_status = validations[0].status if validations else None
    passed = sum(1 for item in validations if item.status == "PASSED")
    pass_rate = (passed / len(validations) * 100) if validations else None
    rounded = round(pass_rate, 1) if pass_rate is not None else None
    alert = None
    if rounded is not None and len(validations) >= 4 and rounded < 50:
        alert = f"Validation pass rate is {rounded}% across the last {len(validations)} runs."
        notify_alert(alert)
    return DashboardStats(
        total_events=len(events),
        active=approved,
        draft=draft,
        in_review=in_review,
        deprecated=deprecated,
        validations=len(validations),
        last_status=last_status,
        pass_rate=rounded,
        alert=alert,
    )


def _window(limit: int, offset: int, cap: int = 100) -> tuple[int, int]:
    return min(max(limit, 1), cap), max(offset, 0)


@router.get("/events", response_model=EventPage)
def list_events(
    q: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    limit, offset = _window(limit, offset)
    query = _event_query(db)
    if q:
        like = f"%{q}%"
        query = query.filter((Event.event_name.ilike(like)) | (Event.description.ilike(like)))
    if status:
        wanted = status.upper()
        if wanted == "APPROVED":
            query = query.filter(Event.status.in_(["APPROVED", "ACTIVE"]))
        else:
            query = query.filter(Event.status == wanted)
    total = query.count()
    rows = query.order_by(Event.event_name.asc()).offset(offset).limit(limit).all()
    return EventPage(
        items=[event_to_summary(event) for event in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_name}", response_model=EventContract)
def get_event(event_name: str, db: Session = Depends(get_db)):
    return event_to_contract(_get_event(db, event_name))


@router.get("/events/{event_name}/versions", response_model=list[EventVersionOut])
def list_versions(event_name: str, db: Session = Depends(get_db)):
    _get_event(db, event_name)
    rows = (
        db.query(EventVersion)
        .filter(EventVersion.event_name == event_name)
        .order_by(EventVersion.id.desc())
        .all()
    )
    return [
        EventVersionOut(
            id=row.id,
            event_name=row.event_name,
            version=row.version,
            status=row.status,
            action=row.action,
            actor=row.actor,
            comment=row.comment or "",
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/events/{event_name}/diff", response_model=ContractDiff)
def diff_event(event_name: str, db: Session = Depends(get_db)):
    event = _get_event(db, event_name)
    approved = last_approved_snapshot(db, event_name)
    return ContractDiff(
        baseline_version=(approved or {}).get("version") if approved else None,
        changes=[DiffChange(**change) for change in contract_diff(snapshot(event), approved)],
    )


@router.get("/events/{event_name}/schema", response_model=JsonSchemaOut)
def event_schema(event_name: str, db: Session = Depends(get_db)):
    contract = event_to_contract(_get_event(db, event_name)).model_dump()
    return JsonSchemaOut(event_name=event_name, json_schema=json_schema(contract))


@router.get("/events/{event_name}/types", response_model=PublishedType)
def event_types(event_name: str, language: str = "typescript", db: Session = Depends(get_db)):
    contract = event_to_contract(_get_event(db, event_name)).model_dump()
    try:
        source = render_type(contract, language.lower())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PublishedType(language=language.lower(), source=source)


@router.get("/events/{event_name}/usages", response_model=list[UsageSummary])
def event_usages(event_name: str, db: Session = Depends(get_db)):
    _get_event(db, event_name)
    rows = (
        db.query(EventUsage)
        .filter(EventUsage.event_name == event_name)
        .order_by(EventUsage.id.desc())
        .all()
    )
    grouped: dict[str, UsageSummary] = {}
    for row in rows:
        key = row.repository or "unspecified"
        current = grouped.get(key)
        if current is None:
            grouped[key] = UsageSummary(
                repository=key,
                count=1,
                last_file=row.file or "",
                last_line=row.line,
            )
        else:
            current.count += 1
    return list(grouped.values())


@router.post("/events", response_model=EventContract)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("editor")),
):
    validate_contract_shape(payload.event_name, payload.parameters)
    existing = db.query(Event).filter(Event.event_name == payload.event_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Event already exists")
    event = Event(
        event_name=payload.event_name,
        description=payload.description,
        version=payload.version,
        status="DRAFT",
        replacement=payload.replacement,
        platforms=",".join(payload.platforms),
        aliases=",".join(item.strip() for item in payload.aliases if item.strip()),
        owner=payload.owner.strip() or principal.email or principal.subject,
        trigger=payload.trigger,
    )
    replace_parameters(event, payload.parameters)
    db.add(event)
    db.flush()
    record_version(db, event, principal, "create")
    record_audit(db, principal, "create", event.event_name, None, snapshot(event))
    db.commit()
    db.refresh(event)
    return event_to_contract(event)


@router.patch("/events/{event_name}", response_model=EventContract)
def update_event(
    event_name: str,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("editor")),
):
    event = _get_event(db, event_name)
    if event.status not in {"DRAFT", "REVIEW"}:
        raise HTTPException(status_code=409, detail="Approved contracts must be revised before editing")
    require_revision(event, payload.expected_revision)
    before = snapshot(event)
    if payload.description is not None:
        event.description = payload.description
    if payload.version is not None:
        event.version = payload.version
    if payload.replacement is not None:
        event.replacement = payload.replacement
    if payload.platforms is not None:
        event.platforms = ",".join(payload.platforms)
    if payload.aliases is not None:
        event.aliases = ",".join(item.strip() for item in payload.aliases if item.strip())
    if payload.owner is not None:
        event.owner = payload.owner.strip()
    if payload.trigger is not None:
        event.trigger = payload.trigger
    if payload.parameters is not None:
        validate_contract_shape(event.event_name, payload.parameters)
        replace_parameters(event, payload.parameters)
    record_audit(db, principal, "update", event.event_name, before, snapshot(event))
    db.commit()
    db.refresh(event)
    return event_to_contract(event)


@router.post("/events/{event_name}/transitions", response_model=EventContract)
def transition_event(
    event_name: str,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_user),
):
    event = _get_event(db, event_name)
    transition(
        db,
        event,
        payload.action,
        principal,
        payload.replacement,
        payload.comment,
        payload.expected_revision,
    )
    db.commit()
    db.refresh(event)
    return event_to_contract(event)


@router.post("/events/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest, db: Session = Depends(get_db)):
    result = await generate_events(payload.requirement, get_contracts_map(db), payload.platform)
    meta = result.get("ai_meta") or {}
    if meta.get("fallback_reason"):
        record_ai_failure()
    db.add(
        AiRun(
            model=meta.get("model") or "",
            prompt_version=meta.get("prompt_version") or "",
            input_hash=meta.get("input_hash") or "",
            requirement_redacted=meta.get("requirement_redacted") or "",
            output_json=json.dumps({"events": result.get("events") or [], "source": result.get("source")}),
            latency_ms=int(meta.get("latency_ms") or 0),
            fallback_reason=meta.get("fallback_reason") or "",
            status=result.get("source") or "",
            trace_id=current_trace_id(),
        )
    )
    db.commit()
    return GenerateResponse(**result)


@router.post("/validate", response_model=ValidateResponse)
def validate(
    payload: ValidateCodeRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    if payload.sample:
        try:
            code = load_sample_code(payload.sample)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif payload.code:
        code = payload.code
    else:
        raise HTTPException(status_code=400, detail="Provide code or sample=valid|invalid")

    rows = db.query(TrackingFunction).order_by(TrackingFunction.name.asc()).all()
    wrappers = [
        {"name": row.name, "event_arg": row.event_arg, "params_arg": row.params_arg, "style": row.style}
        for row in rows
    ]
    result = validate_code(
        code,
        get_contracts_map(db),
        platform=payload.platform,
        wrappers=wrappers or None,
    )
    repository = payload.repository.strip() or ("sample:" + payload.sample if payload.sample else "api")
    record = ValidationResult(
        status=result["status"],
        source="sample" if payload.sample else "code",
        actor=principal.email or principal.subject,
        events_found=result["events_found"],
        issues_count=len([issue for issue in result["issues"] if issue.get("severity") == "error"]),
        report_json=json.dumps(result),
        trace_id=current_trace_id(),
    )
    db.add(record)
    db.flush()
    _record_usages(db, result.get("events") or [], repository, record.id, principal)
    db.commit()
    record_validation(result["status"])
    db.refresh(record)
    return ValidateResponse(
        id=record.id,
        status=result["status"],
        events_found=result["events_found"],
        issues=[ValidationIssue(**issue) for issue in result["issues"]],
        events=[FoundEvent(**event) for event in result["events"]],
        suggested_implementation=result.get("suggested_implementation"),
        summary=result.get("summary") or format_report(result),
    )


@router.get("/validation/{validation_id}", response_model=ValidationResultOut)
def get_validation(validation_id: int, db: Session = Depends(get_db)):
    row = db.query(ValidationResult).filter(ValidationResult.id == validation_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Validation not found")
    return ValidationResultOut(
        id=row.id,
        status=row.status,
        source=row.source,
        events_found=row.events_found,
        issues_count=row.issues_count,
        report=json.loads(row.report_json or "{}"),
        created_at=row.created_at,
    )


@router.get("/validation", response_model=list[ValidationResultOut])
def list_validations(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(ValidationResult).order_by(ValidationResult.id.desc()).limit(min(limit, 100)).all()
    return [
        ValidationResultOut(
            id=row.id,
            status=row.status,
            source=row.source,
            events_found=row.events_found,
            issues_count=row.issues_count,
            report=json.loads(row.report_json or "{}"),
            created_at=row.created_at,
        )
        for row in rows
    ]


def _audit_out(row: AuditLog) -> AuditEntry:
    return AuditEntry(
        id=row.id,
        actor=row.actor,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        comment=row.comment or "",
        created_at=row.created_at,
    )


@router.get("/audit", response_model=AuditPage)
def list_audit(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    limit, offset = _window(limit, offset)
    query = db.query(AuditLog)
    total = query.count()
    rows = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
    return AuditPage(items=[_audit_out(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/audit/export", response_model=list[AuditEntry])
def export_audit(db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.id.asc()).limit(1000).all()
    return [_audit_out(row) for row in rows]


def _decision_out(row: RecommendationDecision) -> RecommendationDecisionOut:
    return RecommendationDecisionOut(
        id=row.id,
        actor=row.actor,
        requirement=row.requirement,
        event_name=row.event_name,
        decision=row.decision,
        created_at=row.created_at,
    )


@router.get("/recommendations", response_model=RecommendationPage)
def list_recommendations(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    limit, offset = _window(limit, offset)
    query = db.query(RecommendationDecision)
    total = query.count()
    rows = query.order_by(RecommendationDecision.id.desc()).offset(offset).limit(limit).all()
    return RecommendationPage(items=[_decision_out(row) for row in rows], total=total, limit=limit, offset=offset)


@router.post("/recommendations", response_model=RecommendationDecisionOut)
def decide_recommendation(
    payload: RecommendationRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("editor")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = (idempotency_key or "").strip() or None
    request_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    if key:
        existing = db.query(RecommendationDecision).filter(RecommendationDecision.idempotency_key == key).first()
        if existing is not None:
            if existing.request_hash and existing.request_hash != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different request")
            if existing.response_json:
                return RecommendationDecisionOut.model_validate_json(existing.response_json)
            return _decision_out(existing)
    decision = payload.decision.strip().lower()
    if decision not in {"accepted", "rejected"}:
        raise HTTPException(status_code=422, detail="Decision must be accepted or rejected")
    event_name = payload.event.event_name if payload.event else ""
    if decision == "accepted":
        if payload.event is None:
            raise HTTPException(status_code=422, detail="Accepted recommendations need an event")
        validate_contract_shape(payload.event.event_name, payload.event.parameters)
        if db.query(Event).filter(Event.event_name == payload.event.event_name).first():
            raise HTTPException(status_code=409, detail="Event already exists")
        event = Event(
            event_name=payload.event.event_name,
            description=payload.event.description,
            version="1.0",
            status="DRAFT",
            platforms=",".join(payload.event.platforms),
            owner=principal.email or principal.subject,
            trigger=payload.event.trigger,
        )
        replace_parameters(event, payload.event.parameters)
        db.add(event)
        db.flush()
        record_version(db, event, principal, "create")
        record_audit(db, principal, "create", event.event_name, None, snapshot(event))
    row = RecommendationDecision(
        actor=principal.email or principal.subject,
        requirement=payload.requirement,
        event_name=event_name,
        decision=decision,
        idempotency_key=key,
        request_hash=request_hash if key else "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    body = _decision_out(row)
    if key:
        row.response_json = body.model_dump_json()
        db.commit()
    return body


@router.get("/tracking-functions")
def list_tracking_functions(db: Session = Depends(get_db)):
    rows = db.query(TrackingFunction).order_by(TrackingFunction.name.asc()).all()
    return {
        "functions": [
            {"name": row.name, "style": row.style, "event_arg": row.event_arg, "params_arg": row.params_arg}
            for row in rows
        ]
    }


@router.post("/tracking-functions")
def register_tracking_function(
    payload: TrackingFunctionIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("editor")),
):
    if not FUNCTION_NAME_RE.match(payload.name):
        raise HTTPException(status_code=422, detail="Function name must be an identifier")
    if db.query(TrackingFunction).filter(TrackingFunction.name == payload.name).first() is None:
        db.add(
            TrackingFunction(
                name=payload.name,
                style=payload.style or "auto",
                event_arg=payload.event_arg,
                params_arg=payload.params_arg,
            )
        )
        record_audit(
            db,
            principal,
            "register-tracker",
            payload.name,
            None,
            {"name": payload.name},
        )
        db.commit()
    rows = db.query(TrackingFunction).order_by(TrackingFunction.name.asc()).all()
    return {
        "functions": [
            {"name": row.name, "style": row.style, "event_arg": row.event_arg, "params_arg": row.params_arg}
            for row in rows
        ]
    }


def _validation_response(record: ValidationResult, result: dict) -> ValidateResponse:
    return ValidateResponse(
        id=record.id,
        status=result["status"],
        events_found=result["events_found"],
        issues=[ValidationIssue(**issue) for issue in result["issues"]],
        events=[FoundEvent(**event) for event in result["events"]],
        suggested_implementation=result.get("suggested_implementation"),
        summary=result.get("summary") or format_report(result),
    )


@router.post("/validate/payload", response_model=ValidateResponse)
def validate_event_payload(
    payload: PayloadCheckRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("viewer")),
):
    result = validate_payload(payload.event_name, payload.payload, get_contracts_map(db))
    repository = payload.repository.strip() or "runtime"
    record = ValidationResult(
        status=result["status"],
        source="payload",
        actor=principal.email or principal.subject,
        events_found=result["events_found"],
        issues_count=len([issue for issue in result["issues"] if issue.get("severity") == "error"]),
        report_json=json.dumps(result),
        trace_id=current_trace_id(),
    )
    db.add(record)
    db.flush()
    _record_usages(db, result.get("events") or [], repository, record.id, principal)
    db.commit()
    record_validation(result["status"])
    db.refresh(record)
    return _validation_response(record, result)


@router.get("/queue", response_model=list[QueueItem])
def review_queue(db: Session = Depends(get_db), principal: Principal = Depends(get_current_user)):
    items: list[QueueItem] = []
    seen: set[str] = set()
    if principal.has("approver"):
        waiting = _event_query(db).filter(Event.status == "REVIEW").order_by(Event.event_name.asc()).all()
        for event in waiting:
            seen.add(event.event_name)
            items.append(
                QueueItem(
                    event_name=event.event_name,
                    status=event.status,
                    owner=event.owner or "",
                    reason="Awaiting approval",
                )
            )
    if principal.has("editor"):
        owner = principal.email or principal.subject
        drafts = (
            _event_query(db)
            .filter(Event.status == "DRAFT", Event.owner == owner)
            .order_by(Event.event_name.asc())
            .all()
        )
        for event in drafts:
            if event.event_name in seen:
                continue
            items.append(
                QueueItem(
                    event_name=event.event_name,
                    status=event.status,
                    owner=event.owner or "",
                    reason="Your draft",
                )
            )
    return items


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread: bool = False,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.audience.in_(_audiences(principal)))
    if unread:
        query = query.filter(Notification.read.is_(False))
    rows = query.order_by(Notification.id.desc()).limit(50).all()
    return [_notification_out(row) for row in rows]


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_user),
):
    row = db.query(Notification).filter(Notification.id == notification_id).first()
    if row is None or row.audience not in _audiences(principal):
        raise HTTPException(status_code=404, detail="Notification not found")
    row.read = True
    db.commit()
    db.refresh(row)
    return _notification_out(row)


@router.get("/ai-runs", response_model=list[AiRunOut])
def list_ai_runs(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(AiRun).order_by(AiRun.id.desc()).limit(min(max(limit, 1), 100)).all()
    return [
        AiRunOut(
            id=row.id,
            model=row.model,
            prompt_version=row.prompt_version,
            input_hash=row.input_hash,
            requirement_redacted=row.requirement_redacted,
            latency_ms=row.latency_ms,
            fallback_reason=row.fallback_reason or "",
            status=row.status,
            created_at=row.created_at,
        )
        for row in rows
    ]
