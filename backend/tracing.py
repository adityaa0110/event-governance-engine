"""Request trace id shared by logs, audits, and AI runs."""

from __future__ import annotations

from contextvars import ContextVar

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def set_trace_id(value: str) -> None:
    _trace_id.set(value)


def current_trace_id() -> str:
    return _trace_id.get()
