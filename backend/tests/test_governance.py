import uuid

import pytest

from auth import Principal, get_current_user
from main import app
from validator.engine import load_contracts_from_disk, validate_code
from ai.evaluate import evaluate


def test_health_ready_and_config(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/ready").json()["status"] == "ready"
    assert client.get("/api/config").json()["auth_required"] is False
    assert "admin" in client.get("/api/me").json()["roles"]


def test_seeded_catalogue_and_validation_samples(client):
    events = client.get("/api/events").json()["items"]
    names = {event["event_name"] for event in events}
    assert {"purchase_button_clicked", "buy_now", "plan_selected"} <= names
    approved = next(event for event in events if event["event_name"] == "purchase_button_clicked")
    assert approved["status"] == "APPROVED"

    invalid = client.post("/api/validate", json={"sample": "invalid"}).json()
    valid = client.post("/api/validate", json={"sample": "valid"}).json()
    assert invalid["status"] == "FAILED"
    assert valid["status"] == "PASSED"
    assert "purchase_button_clicked" in invalid["suggested_implementation"]


def test_contract_workflow_versioning_and_audit(client):
    name = f"promo_viewed_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/api/events",
        json={
            "event_name": name,
            "description": "Customer sees a promotion",
            "platforms": ["APP"],
            "parameters": {"promo_id": {"type": "string", "required": True}},
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "DRAFT"

    assert client.post(f"/api/events/{name}/transitions", json={"action": "submit"}).json()["status"] == "REVIEW"
    assert client.post(f"/api/events/{name}/transitions", json={"action": "approve"}).json()["status"] == "APPROVED"
    revised = client.post(f"/api/events/{name}/transitions", json={"action": "revise"})
    assert revised.status_code == 200
    assert revised.json()["status"] == "DRAFT"
    assert revised.json()["version"] == "1.1"

    edited = client.patch(
        f"/api/events/{name}",
        json={"parameters": {}, "version": "1.1"},
    )
    assert edited.status_code == 200
    assert client.post(f"/api/events/{name}/transitions", json={"action": "submit"}).status_code == 200
    blocked = client.post(f"/api/events/{name}/transitions", json={"action": "approve"})
    assert blocked.status_code == 409

    assert client.patch(f"/api/events/{name}", json={"version": "2.0"}).status_code == 200
    assert client.post(f"/api/events/{name}/transitions", json={"action": "approve"}).json()["status"] == "APPROVED"
    deprecated = client.post(
        f"/api/events/{name}/transitions",
        json={"action": "deprecate", "replacement": "purchase_button_clicked"},
    )
    assert deprecated.json()["status"] == "DEPRECATED"
    assert any(entry["entity_id"] == name for entry in client.get("/api/audit").json()["items"])
    assert client.get(f"/api/events/{name}/versions").json()


def test_viewer_cannot_create_contract(client):
    app.dependency_overrides[get_current_user] = lambda: Principal(
        subject="viewer",
        email="viewer@example.com",
        name="Viewer",
        roles={"viewer"},
    )
    response = client.post(
        "/api/events",
        json={"event_name": "viewer_event", "parameters": {}},
    )
    assert response.status_code == 403


def test_authentication_is_required_when_enabled(client, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "false")
    response = client.get("/api/stats")
    assert response.status_code == 401
    assert client.get("/api/health").status_code == 200
    assert client.get("/metrics").status_code == 401
    assert client.get("/docs").status_code == 401


def test_rate_limit_applies_when_auth_is_required(client, monkeypatch):
    from observability import _HITS

    _HITS.clear()
    monkeypatch.setenv("AUTH_DISABLED", "false")
    monkeypatch.setenv("RATE_LIMIT", "2")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/stats").status_code == 429


def test_disk_validator_and_recommender():
    contracts = load_contracts_from_disk()
    invalid = validate_code('trackEvent("buyNowClicked", { productId: 1 });', contracts)
    assert invalid["status"] == "FAILED"
    assert any(issue["expected"] == "purchase_button_clicked" for issue in invalid["issues"])
    assert all(case["passed"] for case in evaluate(contracts))


def test_babel_parser_understands_typescript():
    from validator.parser import parse_with_babel

    parsed = parse_with_babel(
        """
        export function click(plan: { id: string }) {
          trackEvent("plan_selected", {
            plan_id: plan.id as string,
            plan_name: "Fiber",
            price: 10,
          });
        }
        """
    )
    if parsed is None:
        pytest.skip("Babel parser dependencies are not installed")
    assert parsed[0]["event_name"] == "plan_selected"
    assert parsed[0]["param_types"]["plan_id"] == "unknown"


def test_seed_keeps_catalogue_edits(client):
    from database import SessionLocal
    from models import Event
    from seed import seed_database

    db = SessionLocal()
    event = db.query(Event).filter(Event.event_name == "plan_selected").one()
    event.description = "edited locally"
    db.commit()
    seed_database(db)
    db.expire_all()
    event = db.query(Event).filter(Event.event_name == "plan_selected").one()
    assert event.description == "edited locally"
    db.close()


def test_reject_comment_diff_and_recommendation(client):
    name = f"banner_seen_{uuid.uuid4().hex[:8]}"
    assert client.post(
        "/api/events",
        json={"event_name": name, "description": "Banner", "parameters": {"banner_id": {"type": "string", "required": True}}},
    ).status_code == 200
    assert client.post(f"/api/events/{name}/transitions", json={"action": "submit"}).status_code == 200
    assert client.post(f"/api/events/{name}/transitions", json={"action": "reject"}).status_code == 422
    rejected = client.post(
        f"/api/events/{name}/transitions",
        json={"action": "reject", "comment": "Needs a clearer trigger"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "DRAFT"
    versions = client.get(f"/api/events/{name}/versions").json()
    assert any(item["action"] == "reject" and item["comment"] == "Needs a clearer trigger" for item in versions)

    assert client.post(f"/api/events/{name}/transitions", json={"action": "submit"}).status_code == 200
    assert client.post(f"/api/events/{name}/transitions", json={"action": "approve"}).status_code == 200
    assert client.post(f"/api/events/{name}/transitions", json={"action": "revise"}).status_code == 200
    assert client.patch(f"/api/events/{name}", json={"description": "Banner impression"}).status_code == 200
    diff = client.get(f"/api/events/{name}/diff").json()
    assert diff["baseline_version"] == "1.0"
    assert any(change["field"] == "description" for change in diff["changes"])

    draft_name = f"help_opened_{uuid.uuid4().hex[:8]}"
    accepted = client.post(
        "/api/recommendations",
        json={
            "requirement": "Open help",
            "decision": "accepted",
            "event": {
                "event_name": draft_name,
                "description": "Help article opened",
                "parameters": {"article_id": {"type": "string", "required": True}},
            },
        },
    )
    assert accepted.status_code == 200
    assert client.get(f"/api/events/{draft_name}").json()["status"] == "DRAFT"
    assert client.post(
        "/api/recommendations",
        json={"requirement": "Open help", "decision": "rejected", "event": {"event_name": draft_name, "description": "skip"}},
    ).status_code == 200
    assert any(item["decision"] == "accepted" and item["event_name"] == draft_name for item in client.get("/api/recommendations").json()["items"])
    assert client.post(
        "/api/recommendations",
        json={
            "requirement": "Open help",
            "decision": "accepted",
            "event": {"event_name": draft_name, "description": "again"},
        },
    ).status_code == 409


def test_registered_wrapper_and_other_languages(client):
    from pathlib import Path

    assert client.post("/api/tracking-functions", json={"name": "logPurchase"}).status_code == 200
    wrapped = client.post(
        "/api/validate",
        json={"code": 'logPurchase("plan_selected", { plan_id: "p", plan_name: "Fiber", price: 10 });'},
    ).json()
    assert wrapped["status"] == "PASSED"

    root = Path(__file__).resolve().parents[2]
    contracts = load_contracts_from_disk()
    for relative in ("sample-project/valid/PlanSelected.kt", "sample-project/valid/CheckoutStarted.java", "sample-project/valid/BuyNow.swift"):
        code = (root / relative).read_text(encoding="utf-8")
        result = validate_code(code, contracts, filename=relative)
        assert result["status"] == "PASSED", result

    changed = validate_code(
        'trackEvent("buy_now", { productId: 1 });\ntrackEvent("purchase_button_clicked", { product_id: "1", product_category: "broadband", price: 1, customer_type: "new" });',
        contracts,
        changed_lines={2},
    )
    assert changed["status"] == "PASSED"
    assert changed["events_found"] == 1


def test_changed_line_diff_parser():
    from validator.diff import parse_unified_diff

    parsed = parse_unified_diff(
        "diff --git a/a.kt b/a.kt\n+++ b/a.kt\n@@ -0,0 +4,2 @@\n+one\n+two\n"
    )
    assert parsed["a.kt"] == {4, 5}


def test_llm_failure_is_visible(monkeypatch):
    import asyncio

    from ai import event_analyzer

    async def failed(*_args, **_kwargs):
        return None, "upstream timeout"

    monkeypatch.setattr(event_analyzer, "llm_generate", failed)
    result = asyncio.run(event_analyzer.generate_events("Open the help center article.", {}, None))
    assert result["source"] == "fallback"
    assert result["llm_error"] == "upstream timeout"
    assert "upstream timeout" in result["message"]


def test_low_pass_rate_sets_alert(client):
    from database import SessionLocal
    from models import ValidationResult

    db = SessionLocal()
    for _ in range(4):
        db.add(ValidationResult(status="FAILED", source="test", events_found=1, issues_count=1, report_json="{}"))
    db.commit()
    db.close()
    stats = client.get("/api/stats").json()
    assert stats["alert"]


def test_revision_conflict_and_idempotent_recommendation(client):
    name = f"offer_seen_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/api/events",
        json={"event_name": name, "description": "Offer", "parameters": {"offer_id": {"type": "string", "required": True}}},
    ).json()
    stale = client.patch(
        f"/api/events/{name}",
        json={"description": "Offer updated", "expected_revision": created["revision"] + 5},
    )
    assert stale.status_code == 409
    updated = client.patch(
        f"/api/events/{name}",
        json={"description": "Offer updated", "expected_revision": created["revision"]},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == created["revision"] + 1

    key = uuid.uuid4().hex
    body = {
        "requirement": "Share a referral",
        "decision": "accepted",
        "event": {"event_name": f"referral_{key[:6]}", "description": "Referral shared", "parameters": {}},
    }
    headers = {"Idempotency-Key": key}
    first = client.post("/api/recommendations", json=body, headers=headers)
    second = client.post("/api/recommendations", json=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    page = client.get("/api/events?limit=1&offset=0").json()
    assert page["limit"] == 1
    assert page["total"] >= 1
    assert len(page["items"]) == 1


def test_redaction_and_migration_roundtrip(tmp_path, monkeypatch):
    from pathlib import Path

    from ai.safety import redact
    from alembic import command
    from alembic.config import Config

    assert redact("mail me at ada@example.com token sk-abcdefghij") == "mail me at [email] token [secret]"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'migrate.db'}")
    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
