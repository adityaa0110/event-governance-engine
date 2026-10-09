"""Request logging, request IDs, rate limits, and a small Prometheus metrics endpoint."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import Counter, defaultdict

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from auth import verify_oidc_token
from config import alert_webhook_url, auth_disabled, cors_origins
from tracing import set_trace_id

logger = logging.getLogger("governance")
REQUESTS: Counter[tuple[str, str, int]] = Counter()
VALIDATIONS: Counter[str] = Counter()
AI_FAILURES = 0
DURATION_BUCKETS = (50, 100, 250, 500, 1000, 2500)
DURATION_COUNTS: Counter[str] = Counter()
DURATION_SUM = 0.0
DURATION_TOTAL = 0
_HITS: dict[str, list[float]] = defaultdict(list)
_OPEN_PATHS = {"/api/health", "/api/ready", "/api/config", "/api/demo/prd"}
_PROTECTED_DOCS = {"/metrics", "/docs", "/redoc", "/openapi.json"}


def _rate_limit() -> int:
    try:
        return max(1, int(os.getenv("RATE_LIMIT", "120")))
    except ValueError:
        return 120


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or auth_disabled() or request.url.path in _OPEN_PATHS:
            return await call_next(request)
        now = time.time()
        host = request.client.host if request.client else "unknown"
        recent = [stamp for stamp in _HITS[host] if now - stamp < 60]
        if len(recent) >= _rate_limit():
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        recent.append(now)
        _HITS[host] = recent
        return await call_next(request)


class ProtectedDocsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if auth_disabled() or request.method == "OPTIONS" or path not in _PROTECTED_DOCS:
            return await call_next(request)
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        try:
            verify_oidc_token(header.split(" ", 1)[1].strip())
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return await call_next(request)


def trace_id_from(header: str) -> str:
    parts = (header or "").split("-")
    if len(parts) >= 4 and len(parts[1]) == 32:
        return parts[1]
    return uuid.uuid4().hex


def observe_duration(duration_ms: float) -> None:
    global DURATION_SUM, DURATION_TOTAL
    DURATION_SUM += duration_ms
    DURATION_TOTAL += 1
    for bucket in DURATION_BUCKETS:
        if duration_ms <= bucket:
            DURATION_COUNTS[str(bucket)] += 1
    DURATION_COUNTS["+Inf"] += 1


def record_validation(status: str) -> None:
    VALIDATIONS[status] += 1


def record_ai_failure() -> None:
    global AI_FAILURES
    AI_FAILURES += 1


def notify_alert(message: str) -> None:
    url = alert_webhook_url()
    if not url or not message:
        return
    try:
        import httpx

        httpx.post(url, json={"alert": message, "service": "event-governance-engine"}, timeout=2.0)
    except Exception:
        logger.exception("alert webhook failed")


class OriginGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if auth_disabled() or request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        origin = request.headers.get("origin")
        if origin and origin not in cors_origins():
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        return await call_next(request)


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        trace_id = trace_id_from(request.headers.get("traceparent", ""))
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        set_trace_id(trace_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.exception(
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": elapsed_ms,
                    }
                )
            )
            raise
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        observe_duration(elapsed_ms)
        REQUESTS[(request.method, request.url.path, response.status_code)] += 1
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": elapsed_ms,
                }
            )
        )
        response.headers["x-request-id"] = request_id
        response.headers["x-trace-id"] = trace_id
        return response


def metrics_text() -> str:
    lines = [
        "# HELP governance_http_requests_total HTTP requests served",
        "# TYPE governance_http_requests_total counter",
    ]
    for (method, path, status), count in sorted(REQUESTS.items()):
        lines.append(
            'governance_http_requests_total{method="%s",path="%s",status="%s"} %s'
            % (method, path, status, count)
        )
    lines.extend(
        [
            "# HELP governance_http_request_duration_ms Request duration",
            "# TYPE governance_http_request_duration_ms histogram",
        ]
    )
    for bucket in (*DURATION_BUCKETS, "+Inf"):
        lines.append(
            'governance_http_request_duration_ms_bucket{le="%s"} %s' % (bucket, DURATION_COUNTS[str(bucket)])
        )
    lines.append("governance_http_request_duration_ms_sum %s" % DURATION_SUM)
    lines.append("governance_http_request_duration_ms_count %s" % DURATION_TOTAL)
    lines.extend(
        [
            "# HELP governance_validations_total Validation runs",
            "# TYPE governance_validations_total counter",
        ]
    )
    for status, count in sorted(VALIDATIONS.items()):
        lines.append('governance_validations_total{status="%s"} %s' % (status, count))
    lines.extend(
        [
            "# HELP governance_ai_failures_total AI recommendation failures",
            "# TYPE governance_ai_failures_total counter",
            "governance_ai_failures_total %s" % AI_FAILURES,
        ]
    )
    return "\n".join(lines) + "\n"
