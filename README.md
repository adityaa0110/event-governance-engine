# Event Governance Engine

**AI-Driven Event Governance & Validation Platform**

> Define once. Validate everywhere. Trust your analytics.

Vibeathon-ready MVP: PRD → AI event recommendations → Event contracts → Code validation → CI gate → Central catalogue.

---

## Quick start (presentation)

```bash
# Terminal 1 — API
cd event-governance-engine
chmod +x scripts/*.sh
./scripts/start-backend.sh

# Terminal 2 — UI
./scripts/start-frontend.sh
```

| Surface | URL |
|---------|-----|
| Dashboard | http://127.0.0.1:5174 |
| API docs | http://127.0.0.1:8001/docs |
| Health | http://127.0.0.1:8001/api/health |

**Demo script:** [PRESENTATION.md](PRESENTATION.md)  
**Slides:** [docs/SLIDE_OUTLINE.md](docs/SLIDE_OUTLINE.md)  
**Team plan:** [docs/TEAM_TASK_BOARD.md](docs/TEAM_TASK_BOARD.md)

No LLM key required — a deterministic demo analyzer handles the Buy Now PRD. Optional: copy `.env.example` → `.env` and set `LLM_API_KEY`.

## Production (Docker)

```bash
docker compose up --build
```

The dashboard is served at http://localhost:8080 and over TLS at https://localhost:8443. Put certificates in `deploy/certs` (or set `TLS_CERT_DIR`); an empty directory receives a local certificate when the web container starts. Nginx adds security headers and limits API traffic to 2 requests per second per address. PostgreSQL stores the catalogue. JSON contracts seed missing events only. Alembic is the schema authority: `upgrade head` creates a new database and later revisions upgrade an existing one.

Contracts move from DRAFT to REVIEW to APPROVED. Deprecation requires a different approved replacement, and the contract page lists repositories whose validations already emitted that event. Authentication stays off until `AUTH_DISABLED=false` plus the OIDC settings. Secrets can be supplied with `DATABASE_URL_FILE` and `LLM_API_KEY_FILE`. With authentication on, `/metrics` and the API docs require a bearer token. The API also keeps a per-process limit (`RATE_LIMIT`, default 120/minute) for clients that are not behind Nginx.

```bash
docker compose --profile backup up -d backup
docker compose --profile backup run --rm --entrypoint sh backup /restore.sh
```

Backups run on `BACKUP_INTERVAL_SECONDS` (default one day), keep `BACKUP_RETENTION_DAYS` (default 14), encrypt when `BACKUP_PASSPHRASE` is set, and can copy to `BACKUP_S3_BUCKET`. A failed dump posts to `ALERT_WEBHOOK_URL` when that is set. The restore command loads the newest dump into a temporary database, counts events, and drops that database.

---

## What it demonstrates

1. **Analyze PRD** — recommends `plan_selected`, `purchase_button_clicked`, `checkout_started` and suggests reusing catalogue events  
2. **Catalogue** — contracts with parameters, types, platforms, and statuses DRAFT, REVIEW, APPROVED, DEPRECATED  
3. **Validate** — invalid `buy_now` fails; corrected `purchase_button_clicked` passes  
4. **CLI / CI** — `event-validator scan` + GitHub Action workflow  

---

## CLI

```bash
cd backend && source .venv/bin/activate
python ../validator-cli/event_validator.py scan ../sample-project/invalid   # FAIL
python ../validator-cli/event_validator.py scan ../sample-project/valid     # PASS
```

---

## Architecture

```
PRD / Jira → AI Analyzer → Event Catalogue (contracts)
                              ↓
                     Code Validator → CI PASS/FAIL
```

- **AI:** requirement understanding, reuse/duplicate suggestions, explanations  
- **Rules:** required fields, types, allowed values, naming, deprecation, platform checks, CI exit codes  

---

## Project layout

```
event-governance-engine/
├── backend/           # FastAPI + AI + validator (SQLite locally, PostgreSQL in Docker)
├── frontend/          # React (Vite) dashboard
├── validator-cli/     # CI-friendly scanner
├── event-contracts/   # JSON seed contracts
├── sample-project/    # valid/ + invalid/ demos
├── .github/workflows/ # Event Governance Action
├── docs/              # slides + task board
└── PRESENTATION.md    # 5-minute demo script
```

---

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health |
| GET | `/api/stats` | Dashboard counters |
| GET | `/api/demo/prd` | Seed Buy Now PRD |
| POST | `/api/events/generate` | PRD → events |
| GET | `/api/events?q=&status=` | Search catalogue, one status at a time, 50 per page |
| GET | `/api/events/{name}` | Contract detail |
| GET | `/api/events/{name}/schema` | JSON Schema for an approved contract |
| GET | `/api/events/{name}/types?language=` | TypeScript, Kotlin, or Swift |
| GET | `/api/events/{name}/usages` | Repositories whose validations emitted the event |
| GET | `/api/queue` | Drafts you own and contracts waiting for approval |
| POST | `/api/validate` | Validate code or `sample=valid\|invalid` |
| POST | `/api/validate/payload` | Validate a runtime payload |
| GET | `/api/validation/{id}` | Stored report |

---

## Success metrics (prototype)

- Consistency: 5 Buy Now names → 1 standard event  
- Pre-merge catch: invalid sample fails CI/validator  
- Effort: automated seconds vs manual review  

---

## Tagline

**Stop fixing analytics after production. Validate events before they ship.**
