"""Redaction and a small circuit breaker for recommendation calls."""

from __future__ import annotations

import re
import time

EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"\b(?:\+?\d[\d\s().-]{8,}\d)\b")
SECRET = re.compile(r"\b(?:sk|pk|api|bearer|token)[_-][A-Za-z0-9]{8,}\b", re.I)
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")

_failures = 0
_open_until = 0.0


def redact(text: str) -> str:
    cleaned = EMAIL.sub("[email]", text or "")
    cleaned = PHONE.sub("[phone]", cleaned)
    cleaned = SECRET.sub("[secret]", cleaned)
    cleaned = CARD.sub("[number]", cleaned)
    return cleaned


def circuit_open() -> bool:
    return time.time() < _open_until


def circuit_success() -> None:
    global _failures, _open_until
    _failures = 0
    _open_until = 0.0


def circuit_failure() -> None:
    global _failures, _open_until
    _failures += 1
    if _failures >= 3:
        _open_until = time.time() + 30
