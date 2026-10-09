"""PRD → standardized event recommendations with deterministic demo fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from typing import Any

import httpx
from pydantic import ValidationError

from ai.safety import circuit_failure, circuit_open, circuit_success, redact
from config import llm_api_key, llm_timeout_seconds
from schemas import GeneratedEvent
from validator.engine import find_similar_event

logger = logging.getLogger("governance.ai")
PROMPT_VERSION = "2026-10-09"

DEMO_EVENTS = [
    {
        "event_name": "plan_selected",
        "description": "Triggered when customer selects a broadband plan",
        "trigger": "User selects a plan from the plan list",
        "platforms": ["APP", "SHOP", "BROADBAND", "TV"],
        "parameters": {
            "plan_id": {"type": "string", "required": True},
            "plan_name": {"type": "string", "required": True},
            "price": {"type": "number", "required": True},
        },
    },
    {
        "event_name": "purchase_button_clicked",
        "description": "Triggered when customer clicks Buy Now",
        "trigger": "User clicks the Buy Now button",
        "platforms": ["APP", "SHOP", "BROADBAND"],
        "parameters": {
            "product_id": {"type": "string", "required": True},
            "product_category": {"type": "string", "required": True},
            "price": {"type": "number", "required": True},
            "customer_type": {"type": "string", "required": True},
        },
    },
    {
        "event_name": "checkout_started",
        "description": "Triggered when customer proceeds to checkout",
        "trigger": "User enters checkout after Buy Now",
        "platforms": ["APP", "SHOP", "BROADBAND", "BOT", "TV"],
        "parameters": {
            "cart_id": {"type": "string", "required": True},
            "product_id": {"type": "string", "required": True},
            "total_amount": {"type": "number", "required": True},
        },
    },
]


def _proposed_event(requirement: str) -> dict[str, Any]:
    stop = {"the", "a", "an", "to", "and", "of", "for", "customer", "user", "open"}
    words = [word for word in re.findall(r"[a-z0-9]+", requirement.lower()) if word not in stop]
    name = "_".join(words[:4] or ["custom", "action"])
    return {
        "event_name": name[:80],
        "description": requirement.strip()[:180],
        "trigger": requirement.strip()[:180],
        "platforms": ["BROADBAND"],
        "parameters": {"item_id": {"type": "string", "required": True}},
    }


def _looks_like_buy_now_prd(text: str) -> bool:
    t = text.lower()
    keywords = ["buy now", "broadband", "checkout", "plan"]
    return sum(1 for k in keywords if k in t) >= 2


def _annotate_with_catalogue(
    events: list[dict[str, Any]], contracts: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    annotated = []
    for ev in events:
        name = ev["event_name"]
        similar, score = find_similar_event(name, contracts)
        reuse = name in contracts and contracts[name].get("status") != "DEPRECATED"
        item = dict(ev)
        if reuse:
            item["reuse_existing"] = True
            item["similar_event"] = name
            item["similarity"] = 1.0
            item["recommendation"] = f"Reuse existing approved event '{name}'."
            # merge catalogue contract params if richer
            catalogue = contracts[name]
            item["parameters"] = catalogue.get("parameters") or item.get("parameters")
            item["platforms"] = catalogue.get("platforms") or item.get("platforms")
            item["description"] = catalogue.get("description") or item.get("description")
        elif similar and score >= 0.7:
            item["reuse_existing"] = True
            item["similar_event"] = similar
            item["similarity"] = score
            item["recommendation"] = (
                f"Possible duplicate. Prefer existing event '{similar}' "
                f"(similarity {int(score * 100)}%)."
            )
            item["event_name"] = similar
            catalogue = contracts[similar]
            item["parameters"] = catalogue.get("parameters") or item.get("parameters")
            item["platforms"] = catalogue.get("platforms") or item.get("platforms")
            item["description"] = catalogue.get("description") or item.get("description")
        else:
            item["reuse_existing"] = False
            item["similar_event"] = similar
            item["similarity"] = score or None
            item["recommendation"] = "No strong catalogue match — review before approving."
        if not item.get("reuse_existing"):
            _flag_parameter_overlap(item, contracts)
        annotated.append(item)
    _flag_repeated_recommendations(annotated)
    return annotated


def _flag_parameter_overlap(item: dict[str, Any], contracts: dict[str, dict[str, Any]]) -> None:
    params = set((item.get("parameters") or {}).keys())
    if len(params) < 2:
        return
    best_name = None
    best_score = 0.0
    for name, contract in contracts.items():
        if name == item.get("event_name") or contract.get("status") == "DEPRECATED":
            continue
        other = set((contract.get("parameters") or {}).keys())
        if not other:
            continue
        score = len(params & other) / len(params | other)
        if score > best_score:
            best_score = score
            best_name = name
    if best_name and best_score >= 0.75:
        item["similar_event"] = best_name
        item["similarity"] = round(best_score, 2)
        item["recommendation"] = (
            f"Parameter set overlaps {int(best_score * 100)}% with '{best_name}'. "
            "Confirm this is not a duplicate."
        )


def _flag_repeated_recommendations(events: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for item in events:
        name = item.get("event_name") or ""
        if name in seen:
            item["reuse_existing"] = True
            item["recommendation"] = f"Duplicate recommendation. '{name}' was already proposed."
        elif name:
            seen.add(name)


def fallback_generate(
    requirement: str, contracts: dict[str, dict[str, Any]], platform: str | None
) -> dict[str, Any]:
    if _looks_like_buy_now_prd(requirement):
        events = DEMO_EVENTS
        message = "Deterministic demo analyzer matched Buy Now / Broadband journey."
    else:
        # generic heuristic: extract verb-like actions
        events = []
        if re.search(r"select|choose", requirement, re.I):
            events.append(DEMO_EVENTS[0])
        if re.search(r"buy|purchase|click", requirement, re.I):
            events.append(DEMO_EVENTS[1])
        if re.search(r"checkout|payment", requirement, re.I):
            events.append(DEMO_EVENTS[2])
        if not events:
            events = [_proposed_event(redact(requirement))]
        message = "Heuristic fallback (no LLM). Customize with LLM_API_KEY for richer analysis."

    normalized = []
    for ev in events:
        item = dict(ev)
        if platform:
            platforms = list(item.get("platforms") or [])
            if platform.upper() not in platforms:
                platforms.append(platform.upper())
            item["platforms"] = platforms
        normalized.append(item)

    annotated = _annotate_with_catalogue(normalized, contracts)
    return {"events": annotated, "source": "fallback", "message": message, "llm_error": None}


async def llm_generate(
    requirement: str, contracts: dict[str, dict[str, Any]], platform: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    api_key = llm_api_key()
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    if not api_key:
        return None, None
    if circuit_open():
        return None, "LLM circuit breaker is open"

    catalogue_names = [
        {"event_name": n, "status": c.get("status"), "description": c.get("description")}
        for n, c in contracts.items()
    ]
    prompt = f"""You are an Event Governance AI for a telecom/digital company.
Analyze the requirement and identify meaningful customer actions that need analytics events.

Naming standards:
- snake_case event names
- prefer reuse of existing catalogue events
- parameters also snake_case
- types: string | number | boolean

Existing catalogue:
{json.dumps(catalogue_names, indent=2)}

Platform hint: {platform or "ALL"}

Requirement:
{redact(requirement)}

Return ONLY valid JSON:
{{
  "events": [
    {{
      "event_name": "...",
      "description": "...",
      "trigger": "...",
      "platforms": ["APP", "SHOP"],
      "parameters": {{
        "product_id": {{"type": "string", "required": true}}
      }}
    }}
  ]
}}
"""
    last_error = "LLM request failed"
    for _attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=llm_timeout_seconds()) as client:
                resp = await client.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": "Return only JSON for event contracts."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                data = json.loads(content)
                events = _valid_events(data.get("events") or [])
                if not events:
                    logger.warning("LLM returned no schema-valid events")
                    last_error = "LLM returned no schema-valid events"
                    continue
                circuit_success()
                annotated = _annotate_with_catalogue(events, contracts)
                return {
                    "events": annotated,
                    "source": "llm",
                    "message": f"Generated via {model}.",
                    "llm_error": None,
                }, None
        except Exception as exc:
            logger.exception("LLM event generation failed")
            last_error = str(exc) or exc.__class__.__name__
    circuit_failure()
    return None, last_error


def _valid_events(events: list[Any]) -> list[dict[str, Any]]:
    valid = []
    for event in events:
        try:
            valid.append(GeneratedEvent.model_validate(event).model_dump())
        except ValidationError:
            logger.warning("Dropped LLM event that failed contract schema validation")
    return valid


def _ai_meta(requirement: str, latency_ms: int, fallback_reason: str, used_model: bool) -> dict[str, Any]:
    redacted = redact(requirement)
    return {
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini") if used_model else "",
        "prompt_version": PROMPT_VERSION,
        "input_hash": hashlib.sha256(redacted.encode()).hexdigest(),
        "requirement_redacted": redacted,
        "latency_ms": latency_ms,
        "fallback_reason": fallback_reason,
    }


async def generate_events(
    requirement: str, contracts: dict[str, dict[str, Any]], platform: str | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    llm_result, llm_error = await llm_generate(requirement, contracts, platform)
    latency_ms = int((time.perf_counter() - started) * 1000)
    if llm_result:
        llm_result["ai_meta"] = _ai_meta(requirement, latency_ms, "", True)
        return llm_result
    fallback = fallback_generate(requirement, contracts, platform)
    fallback["llm_error"] = llm_error
    fallback["ai_meta"] = _ai_meta(requirement, latency_ms, llm_error or "", False)
    if llm_error:
        fallback["message"] = f"LLM failed: {llm_error}. {fallback['message']}"
    return fallback
