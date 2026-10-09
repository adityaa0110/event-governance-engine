from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ParameterSpec(BaseModel):
    type: str = "string"
    required: bool = True
    allowed_values: list[str] = Field(default_factory=list)
    pii: bool = False


class EventContract(BaseModel):
    event_name: str
    description: str = ""
    version: str = "1.0"
    status: str = "DRAFT"
    replacement: str | None = None
    platforms: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    owner: str = ""
    trigger: str = ""
    revision: int = 1
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)


class EventSummary(BaseModel):
    event_name: str
    description: str
    version: str
    status: str
    platforms: list[str]
    replacement: str | None = None
    owner: str = ""
    parameter_count: int = 0


class GenerateRequest(BaseModel):
    requirement: str
    platform: str | None = "BROADBAND"


class GeneratedEvent(BaseModel):
    event_name: str
    description: str
    trigger: str = ""
    platforms: list[str] = Field(default_factory=list)
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)
    reuse_existing: bool = False
    similar_event: str | None = None
    similarity: float | None = None
    recommendation: str = ""


class GenerateResponse(BaseModel):
    events: list[GeneratedEvent]
    source: str = "fallback"
    message: str = ""
    llm_error: str | None = None


class ValidateCodeRequest(BaseModel):
    code: str | None = None
    sample: str | None = None  # "invalid" | "valid"
    platform: str | None = None
    repository: str = ""


class ValidationIssue(BaseModel):
    code: str
    severity: str = "error"
    event: str | None = None
    message: str
    expected: str | None = None
    actual: str | None = None
    file: str | None = None
    line: int | None = None


class FoundEvent(BaseModel):
    event_name: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    param_types: dict[str, str] = Field(default_factory=dict)
    line: int | None = None
    file: str | None = None
    dynamic: bool = False


class ValidateResponse(BaseModel):
    id: int | None = None
    status: str
    events_found: int
    issues: list[ValidationIssue]
    events: list[FoundEvent]
    suggested_implementation: str | None = None
    summary: str = ""


class DashboardStats(BaseModel):
    total_events: int
    active: int
    draft: int = 0
    in_review: int = 0
    deprecated: int
    validations: int
    last_status: str | None = None
    pass_rate: float | None = None
    alert: str | None = None


class EventCreate(BaseModel):
    event_name: str
    description: str = ""
    version: str = "1.0"
    replacement: str | None = None
    platforms: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    owner: str = ""
    trigger: str = ""
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)


class EventUpdate(BaseModel):
    description: str | None = None
    version: str | None = None
    replacement: str | None = None
    platforms: list[str] | None = None
    aliases: list[str] | None = None
    owner: str | None = None
    trigger: str | None = None
    parameters: dict[str, ParameterSpec] | None = None
    expected_revision: int | None = None


class EventPage(BaseModel):
    items: list[EventSummary]
    total: int
    limit: int
    offset: int


class TransitionRequest(BaseModel):
    action: str
    replacement: str | None = None
    comment: str | None = None
    expected_revision: int | None = None


class AuditEntry(BaseModel):
    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: str
    comment: str = ""
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int
    limit: int
    offset: int


class EventVersionOut(BaseModel):
    id: int
    event_name: str
    version: str
    status: str
    action: str
    actor: str
    comment: str = ""
    created_at: datetime


class DiffChange(BaseModel):
    field: str
    before: Any = None
    after: Any = None


class ContractDiff(BaseModel):
    baseline_version: str | None = None
    changes: list[DiffChange] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    requirement: str = ""
    decision: str
    event: GeneratedEvent | None = None


class RecommendationDecisionOut(BaseModel):
    id: int
    actor: str
    requirement: str
    event_name: str
    decision: str
    created_at: datetime


class RecommendationPage(BaseModel):
    items: list[RecommendationDecisionOut]
    total: int
    limit: int
    offset: int


class TrackingFunctionIn(BaseModel):
    name: str
    style: str = "auto"
    event_arg: int = 0
    params_arg: int = 1


class PrincipalOut(BaseModel):
    subject: str
    email: str
    name: str
    roles: list[str]


class PublicConfig(BaseModel):
    auth_required: bool
    issuer: str = ""
    client_id: str = ""
    audience: str = ""
    scopes: str = "openid profile email"


class PayloadCheckRequest(BaseModel):
    event_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    repository: str = ""


class JsonSchemaOut(BaseModel):
    event_name: str
    json_schema: dict[str, Any]


class PublishedType(BaseModel):
    language: str
    source: str


class UsageSummary(BaseModel):
    repository: str
    count: int
    last_file: str = ""
    last_line: int | None = None


class QueueItem(BaseModel):
    event_name: str
    status: str
    owner: str = ""
    reason: str


class NotificationOut(BaseModel):
    id: int
    audience: str
    event_name: str
    kind: str
    message: str
    read: bool
    created_at: datetime


class AiRunOut(BaseModel):
    id: int
    model: str
    prompt_version: str
    input_hash: str
    requirement_redacted: str
    latency_ms: int
    fallback_reason: str
    status: str
    created_at: datetime


class ValidationResultOut(BaseModel):
    id: int
    status: str
    source: str
    events_found: int
    issues_count: int
    report: dict[str, Any]
    created_at: datetime
