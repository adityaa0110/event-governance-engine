"""Runtime configuration loaded from the environment."""

from __future__ import annotations

import os
from pathlib import Path


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def secret(name: str, default: str = "") -> str:
    """Read a secret from NAME_FILE when set, otherwise from the environment."""
    file_path = os.getenv(f"{name}_FILE", "").strip()
    if file_path:
        path = Path(file_path)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    return os.getenv(name, default).strip()


def database_url() -> str:
    configured = secret("DATABASE_URL")
    if configured:
        return configured
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'events.db'}"


def auth_disabled() -> bool:
    return _flag("AUTH_DISABLED", "true")


def cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5174,http://localhost:5174,http://localhost:8080",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


def oidc_issuer() -> str:
    return os.getenv("OIDC_ISSUER", "").rstrip("/")


def oidc_audience() -> str:
    return os.getenv("OIDC_AUDIENCE", "") or os.getenv("OIDC_CLIENT_ID", "")


def oidc_client_id() -> str:
    return os.getenv("OIDC_CLIENT_ID", "")


def oidc_scopes() -> str:
    return os.getenv("OIDC_SCOPES", "openid profile email")


def log_level() -> str:
    return os.getenv("LOG_LEVEL", "INFO").upper()


def audit_retention_days() -> int:
    try:
        return max(0, int(os.getenv("AUDIT_RETENTION_DAYS", "0")))
    except ValueError:
        return 0


def llm_api_key() -> str:
    return secret("LLM_API_KEY") or secret("OPENAI_API_KEY")


def llm_timeout_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("LLM_TIMEOUT_SECONDS", "30")))
    except ValueError:
        return 30.0


def alert_webhook_url() -> str:
    return os.getenv("ALERT_WEBHOOK_URL", "").strip()
