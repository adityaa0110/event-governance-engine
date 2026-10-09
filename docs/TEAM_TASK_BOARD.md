# Team Task Board — 3 People × ~36 Hours

**Product:** Event Governance Engine  
**Goal:** One end-to-end demo — PRD → AI events → contract → bad PR fails CI → fix passes → catalogue  

**Roles**
| ID | Role | Focus |
|----|------|--------|
| **P1** | AI / Backend | LLM, FastAPI, contracts, duplicates |
| **P2** | Validator / CI | Parser, schema checks, CLI, GitHub Action |
| **P3** | UI / Demo | Dashboard, catalogue, PRD upload, rehearsal |

**Shared artifacts (everyone owns quality)**
- `event-contracts/purchase_button_clicked.json` (+ 2–3 more)
- `sample-project/invalid` and `sample-project/valid`
- Demo PRD text for “Buy Now for Broadband”
- This checklist — mark `[x]` as you go

**Priority legend**
- 🔴 P0 — must ship for demo  
- 🟠 P1 — ship if P0 works  
- 🟡 P2 — only after polish time  

---

## Definition of Done (hackathon)

You are done when you can run this without improvising:

1. Paste PRD in UI → see recommended events  
2. Open `purchase_button_clicked` in catalogue with params/types  
3. Run validator (or CI) on **invalid** sample → FAIL with ≥3 clear issues  
4. Run validator on **valid** sample → PASS  
5. Show deprecated/duplicate suggestion at least once (live or screenshot)

---

## Seed content (create in Hour 0–2 — shared)

### Demo PRD (paste into UI)

```text
Feature: Buy Now for Broadband Plans
As a customer, I can select a broadband plan and click Buy Now.
After clicking Buy Now, I proceed to checkout to complete purchase.
Track plan selection, buy click, and checkout start for analytics.
Platform: BROADBAND (also used on APP and SHOP).
```

### Seed contract — `purchase_button_clicked`

```json
{
  "event_name": "purchase_button_clicked",
  "description": "Triggered when customer clicks Buy Now",
  "version": "1.0",
  "status": "ACTIVE",
  "platforms": ["APP", "SHOP", "BROADBAND"],
  "parameters": {
    "product_id": { "type": "string", "required": true },
    "product_category": { "type": "string", "required": true },
    "price": { "type": "number", "required": true },
    "customer_type": { "type": "string", "required": true }
  }
}
```

Also seed: `plan_selected`, `checkout_started`, and deprecated `buy_now` → replacement `purchase_button_clicked`.

### Invalid sample (CI FAIL)

```js
trackEvent("buy_now", {
  productId: 123,
  price: "499"
});
```

### Valid sample (CI PASS)

```js
trackEvent("purchase_button_clicked", {
  product_id: "123",
  product_category: "broadband",
  price: 499,
  customer_type: "existing"
});
```

---

# Day 1 — Hours 0–12  
**Theme:** Skeleton + PRD→Contract path working

## Hours 0–4 — Skeleton working

### All (0:00–0:30)
- [ ] Agree on event name for demo: `purchase_button_clicked`
- [ ] Agree on `trackEvent(name, props)` as the only pattern to parse
- [ ] Create repo folders per README layout
- [ ] Create shared seed PRD + contracts + sample valid/invalid files

### P1 — AI / Backend (0:30–4:00)
- [ ] 🔴 Scaffold FastAPI app (`/health`)
- [ ] 🔴 Define DB models / tables: `events`, `event_parameters`, `validation_results` (SQLite OK if Postgres not ready)
- [ ] 🔴 Seed `purchase_button_clicked` + deprecated `buy_now` via script or SQL
- [ ] 🔴 Stub `POST /api/events/generate` returning hardcoded JSON for the demo PRD (no LLM yet)
- [ ] 🔴 Stub `GET /api/events` and `GET /api/events/{name}`

### P2 — Validator / CI (0:30–4:00)
- [ ] 🔴 Scaffold `validator-cli` with `scan <path>`
- [ ] 🔴 Regex/AST stub: find `trackEvent("…", {…})` and print event name + raw props
- [ ] 🔴 Load contract JSON from `event-contracts/`
- [ ] 🔴 Hardcode first check: unknown event name → FAIL
- [ ] 🔴 Unit-test style: invalid sample fails; valid sample name recognized

### P3 — UI / Demo (0:30–4:00)
- [ ] 🔴 Scaffold Next.js/React app
- [ ] 🔴 Shell layout: Dashboard | Catalogue | Analyze | Validation
- [ ] 🔴 Hardcode catalogue table with seed events (can mock API)
- [ ] 🔴 PRD textarea + “Generate events” button (calls stub or mock)
- [ ] 🟠 Draft 5-minute demo script from `SLIDE_OUTLINE.md`

**Exit gate Hour 4:** Each person can demo their stub in isolation.

---

## Hours 4–10 — PRD → AI → Contract → DB → UI

### P1 (4:00–10:00)
- [ ] 🔴 Wire real LLM call behind `LLMService` (env-based key)
- [ ] 🔴 Prompt: structured JSON only (event_name, description, trigger, parameters[])
- [ ] 🔴 Inject naming standards + existing catalogue names into prompt
- [ ] 🔴 Persist generated contracts to DB
- [ ] 🔴 `POST /api/events` to approve/save
- [ ] 🟠 If time: basic similarity (string/fuzzy) for “buy_now” ≈ “purchase_button_clicked”
- [ ] 🔴 Return generate response shape the UI expects

### P2 (4:00–10:00)
- [ ] 🔴 Parse object properties: keys + literal types (string / number / boolean)
- [ ] 🔴 Checks: missing required, type mismatch, unknown param (warn), deprecated event
- [ ] 🔴 Emit machine-readable report JSON + human-readable console output
- [ ] 🔴 Exit code 1 on FAIL, 0 on PASS (CI-ready)
- [ ] 🟠 Map `productId` → suggest `product_id` (naming)

### P3 (4:00–10:00)
- [ ] 🔴 Connect Analyze page to `POST /api/events/generate`
- [ ] 🔴 Render recommended events list + “view contract”
- [ ] 🔴 Catalogue list from `GET /api/events` (search box)
- [ ] 🔴 Event detail: params table (type, required), platforms, status, version
- [ ] 🟠 Dashboard counters: Active / Deprecated / Last validation

**Exit gate Hour 10:** “Paste PRD → see standardized events in UI” works (LLM or high-quality stub with LLM fallback).

---

## Hours 10–12 — Integration sync (all)

### All together
- [ ] 🔴 Agree API response schemas (freeze for Day 2)
- [ ] 🔴 P3 consumes real P1 APIs (drop mocks where possible)
- [ ] 🔴 P2 validator reads same contracts P1 stores (file export or API)
- [ ] 🔴 Run invalid sample end-to-end once as a team
- [ ] 🔴 Commit: “Day1: generate + catalogue + validator core”

**Day 1 end state**
- Generate path works  
- Catalogue shows seed + generated  
- Validator fails invalid sample for ≥ unknown + missing params  

---

# Day 2 — Hours 12–24  
**Theme:** Validator excellence + CI

## Hours 12–18 — Validator is the hero

### P1 (12:00–18:00)
- [ ] 🔴 `POST /api/validate` accepting code string or sample path id
- [ ] 🔴 Store validation_results; `GET /api/validation/{id}`
- [ ] 🟠 Semantic duplicate detector (embeddings or LLM compare) → suggestion, not hard block
- [ ] 🟠 Platform check: event not approved for BOT → warning/fail
- [ ] 🟡 RAG: top-k catalogue events into generate prompt (pgvector or keyword)

### P2 (12:00–18:00)
- [ ] 🔴 Complete issue codes: `UNKNOWN_EVENT`, `DEPRECATED`, `MISSING_PARAM`, `TYPE_MISMATCH`, `PARAM_NAME`, `PLATFORM`
- [ ] 🔴 Suggested implementation snippet in report (from contract)
- [ ] 🔴 GitHub Action workflow: checkout → install CLI → `scan .` → fail job on issues
- [ ] 🟠 PR comment body (action output or `gh` script)
- [ ] 🔴 Document how judges can re-run locally

### P3 (12:00–18:00)
- [ ] 🔴 Validation results page (issues list with ❌)
- [ ] 🔴 “Run validation” on pasted code or sample toggle (valid/invalid)
- [ ] 🟠 Show similarity/duplicate banner when generate finds existing event
- [ ] 🟠 Deprecation badge in catalogue
- [ ] 🔴 Wire demo happy-path buttons / fixtures to reduce live typing

**Exit gate Hour 18:** Invalid → FAIL report in CLI **and** UI; valid → PASS.

---

## Hours 18–24 — CI + harden demo path

### P1 (18:00–24:00)
- [ ] 🔴 Fallback when LLM down: deterministic mapping for demo PRD (critical)
- [ ] 🔴 Stabilize generate latency (<10s or cached demo response)
- [ ] 🟠 Version field on contracts (`1.0` / `1.1`)
- [ ] 🔴 Error handling: never 500 empty bodies to UI
- [ ] 🔴 Seed script idempotent for fresh machines

### P2 (18:00–24:00)
- [ ] 🔴 Prove Action on a branch with invalid commit (screenshot/log saved)
- [ ] 🔴 Prove Action on valid commit
- [ ] 🟠 Support scanning only `sample-project/` for faster demo
- [ ] 🔴 README section: “How CI works”
- [ ] 🟡 Multi-file scan summary counts (Valid N / Invalid M)

### P3 (18:00–24:00)
- [ ] 🔴 Polish copy for demo screens (clear labels, not marketing clutter)
- [ ] 🔴 Preload demo PRD text in Analyze page
- [ ] 🔴 One-click “Load invalid sample” / “Load valid sample”
- [ ] 🟠 Record 60s backup screen recording if live CI fails
- [ ] 🔴 Align UI labels with slide terminology (Contract, Catalogue, Governance)

### All (23:00–24:00)
- [ ] Full dry-run of 5-minute demo once  
- [ ] List top 3 failure risks + owners (LLM down → P1 fallback; CI flake → P2 local CLI; UI blank → P3 mocks)  
- [ ] Commit: “Day2: validate + CI + demo fixtures”

---

# Day 3 — Hours 24–36  
**Theme:** Polish, metrics, pitch, freeze

## Hours 24–30 — UI polish + story

### P1 (24:00–30:00)
- [ ] 🟠 Duplicate suggestion endpoint used by UI
- [ ] 🟡 Tiny “standards” doc served to prompt (naming snake_case, platforms enum)
- [ ] 🔴 Freeze APIs — no breaking changes after Hour 28
- [ ] 🔴 Prepare prototype metrics from last validation run (counts)

### P2 (24:00–30:00)
- [ ] 🔴 Freeze CLI flags
- [ ] 🟠 Pretty console output for live terminal demo
- [ ] 🔴 Capture FAIL and PASS logs into `docs/demo-artifacts/`
- [ ] 🟡 Optional: second language pattern only if JS path is rock solid (skip if not)

### P3 (24:00–30:00)
- [ ] 🔴 Dashboard: Events / Active / Deprecated / Open issues
- [ ] 🔴 Catalogue search works for `purchase` / `buy`
- [ ] 🔴 Validation page matches CLI issue wording (judges compare)
- [ ] 🟠 Build slides from `SLIDE_OUTLINE.md` (10–12 slides)
- [ ] 🔴 Printable one-pager / README link for judges

**Exit gate Hour 30:** Feature freeze. Only bugfixes and demo reliability.

---

## Hours 30–36 — Killer demo + pitch

### All (30:00–33:00) — rehearsal block
- [ ] Run demo **twice** end-to-end without stopping  
- [ ] Assign speaking parts:
  - [ ] P3: problem + UI drive  
  - [ ] P1: AI / contract explanation  
  - [ ] P2: CI FAIL → PASS moment  
- [ ] Timebox to ≤5 minutes; cut anything not on the happy path  
- [ ] Prepare offline fallback: screenshots + CLI on laptop  

### P1 (33:00–36:00)
- [ ] 🔴 Final check: LLM key + fallback both tested
- [ ] 🔴 Backup generate JSON file for air-gapped demo
- [ ] Support Q&A: architecture, RAG, why not pure LLM validation

### P2 (33:00–36:00)
- [ ] 🔴 Final check: invalid FAIL / valid PASS in <30s
- [ ] 🔴 CI badge or Action run link ready
- [ ] Support Q&A: parser limits, false positives, multi-platform

### P3 (33:00–36:00)
- [ ] 🔴 Slides final + speaker notes
- [ ] 🔴 Demo environment URLs / ports documented
- [ ] 🔴 Reset DB/seed so stage is clean before presentation
- [ ] Close with tagline on last slide

### Ship checklist (Hour 36)
- [ ] README accurate  
- [ ] Seed data resets cleanly  
- [ ] Demo script laminated (or pinned in Slack)  
- [ ] Known limitations listed (honest, short)  
- [ ] No secrets in repo  

---

# Parallel swimlanes (quick view)

```
Hour    P1 AI/Backend              P2 Validator/CI              P3 UI/Demo
0–4     FastAPI + seed + stubs     CLI parse stub               App shell + mocks
4–10    LLM generate + persist     Schema/type/deprecated       Analyze + catalogue live
10–12   API freeze sync            Contract source sync         Drop mocks
12–18   /validate + duplicates     Issue codes + Action         Validation UI
18–24   LLM fallback + harden      Prove CI FAIL/PASS           Demo fixtures + recording
24–30   Freeze + metrics           Demo artifacts               Slides + polish
30–36   Rehearse + Q&A             Rehearse + Q&A               Rehearse + drive UI
```

---

# Decision rules under time pressure

| If behind… | Cut this | Keep this |
|------------|----------|-----------|
| Hour 10 | Real LLM polish | Hardcoded generate for demo PRD |
| Hour 18 | Embeddings / pgvector | Fuzzy/string similar + deprecated check |
| Hour 24 | Real GitHub PR comment | Local CLI FAIL/PASS in terminal |
| Hour 30 | Dashboard beauty | One clear catalogue + validation screen |
| Anytime | Second platform parsers | Single `trackEvent` JS sample |

---

# Communication cadence

| When | What |
|------|------|
| Every 4 hours | 10-min standup: blocked? demo risk? |
| Hour 10, 18, 30 | Exit-gate demo as a team |
| After each gate | Short commit + push |

---

# Ownership of risks

| Risk | Mitigation | Owner |
|------|------------|--------|
| LLM unavailable / slow | Cached/demo fallback response | P1 |
| Parser misses real code | Constrain demo to `trackEvent` samples | P2 |
| UI breaks live | Fixture buttons + screenshots | P3 |
| Scope creep | P0 list only; refuse P2 until freeze | All |
| Conflicting event names | Freeze seed contracts Hour 0 | All |

---

# Post-demo backlog (do not start during Vibeathon)

- Real Jira webhook  
- Multi-language AST (Java/Kotlin/Swift)  
- Runtime volume anomaly detection  
- Auto-open PR with tracking code  
- Production analytics warehouse reconciliation  

---

## Sign-off

| Role | Name | Day 1 gate | Day 2 gate | Feature freeze |
|------|------|------------|------------|----------------|
| P1 | ________ | ☐ | ☐ | ☐ |
| P2 | ________ | ☐ | ☐ | ☐ |
| P3 | ________ | ☐ | ☐ | ☐ |
