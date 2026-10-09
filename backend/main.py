import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from api.routes import public_router, router
from auth import get_current_user
from config import cors_origins, log_level
from database import SessionLocal
from observability import (
    AccessLogMiddleware,
    OriginGuardMiddleware,
    ProtectedDocsMiddleware,
    RateLimitMiddleware,
    metrics_text,
)
from seed import seed_database

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
logging.basicConfig(level=log_level(), format="%(message)s")


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from database import engine

    backend_dir = Path(__file__).resolve().parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    tables = set(inspect(engine).get_table_names())
    # A database created before Alembic owned the schema already has tables.
    # Stamp the last pre-operational revision, then apply later upgrades.
    if "events" in tables and "alembic_version" not in tables:
        command.stamp(cfg, "002_extensions")
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations()
    db = SessionLocal()
    try:
        seed_database(db)
        from governance import prune_audit

        prune_audit(db)
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="Event Governance Engine",
    description="AI-driven event tagging, contracts, and validation",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(OriginGuardMiddleware)
app.add_middleware(ProtectedDocsMiddleware)
app.add_middleware(RateLimitMiddleware)
app.include_router(public_router, prefix="/api")
app.include_router(router, prefix="/api", dependencies=[Depends(get_current_user)])


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return metrics_text()


@app.get("/")
def root():
    return {
        "name": "Event Governance Engine",
        "docs": "/docs",
        "health": "/api/health",
        "tagline": "Define once. Validate everywhere. Trust your analytics.",
    }
