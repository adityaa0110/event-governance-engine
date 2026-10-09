# Presentation guide (5 minutes)

## Before you start

```bash
cd event-governance-engine
./scripts/start-backend.sh   # terminal 1 → http://127.0.0.1:8000
./scripts/start-frontend.sh  # terminal 2 → http://127.0.0.1:5174
```

Optional CLI wow moment (terminal 3):

```bash
cd event-governance-engine/backend && source .venv/bin/activate
python ../validator-cli/event_validator.py scan ../sample-project/invalid
python ../validator-cli/event_validator.py scan ../sample-project/valid
```

Open: **http://127.0.0.1:5174**

---

## Minute-by-minute

| Time | Where | What you say / do |
|------|--------|-------------------|
| 0:00–1:00 | **Dashboard** | Show five platform names for Buy Now. “The problem isn’t naming — it’s analytics contract drift.” |
| 1:00–2:00 | **Analyze PRD** | Click **Load Buy Now PRD** → **Generate events**. Point out reuse of `purchase_button_clicked` + similarity. |
| 2:00–3:00 | **Catalogue** | Open `purchase_button_clicked`. Show required params/types/platforms. Mention deprecated `buy_now`. |
| 3:00–4:00 | **Validate** | Click **Run invalid sample**. Walk issues: UNKNOWN/DEPRECATED, PARAM_NAME, TYPE_MISMATCH, MISSING_PARAM. Show suggested fix. |
| 4:00–5:00 | **Validate** | Click **Run valid sample** → PASS. Optional: show CLI FAIL then PASS. Close: *Define once. Validate everywhere. Trust your analytics.* |

---

## Backup if UI fails

1. API docs: http://127.0.0.1:8000/docs  
2. CLI scan invalid/valid  
3. Screenshots in `docs/` if you capture them before stage  

---

## Likely judge questions

| Question | Answer |
|----------|--------|
| Why not pure LLM validation? | AI for semantics; deterministic rules for CI pass/fail. |
| What if LLM is down? | Demo fallback analyzer still completes the Buy Now journey. |
| Multi-language? | MVP parses `trackEvent` in JS/TS; same contract model extends later. |
| Production path? | Phase 2 Jira/GitHub; Phase 3 runtime volume checks. |
