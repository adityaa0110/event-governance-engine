# Vibeathon Slide Outline

**Working title:** AI-Driven Event Governance & Validation Platform  
**Duration:** ~5–7 minute pitch + optional demo  
**Audience:** Judges (product, engineering, data/analytics)

Use **10–12 slides**. Prefer diagrams and one demo path over feature laundry lists.

---

## Slide 1 — Title

**Title:** Event Governance Engine  
**Subtitle:** From PRD to production — trusted events by design  

**On slide**
- Team of 3 (names / roles)
- Tagline: *Define once. Validate everywhere. Trust your analytics.*
- Platforms in scope: App · Shop · Bot · TV · Broadband

**Speaker note:** Open with the business outcome (trustworthy analytics), not the model name.

---

## Slide 2 — The problem is not “naming”

**Title:** Analytics contract drift

**On slide**
- Table of five platforms × five event names for “Buy Now”
- Callout: same business action, incompatible telemetry
- Second callout: even “correct” names ship with wrong types / missing fields

**Speaker note:** “Different teams use different names” is too small. The real pain is **contract drift** discovered after release.

---

## Slide 3 — Cost of the status quo

**Title:** Today’s flow finds problems too late

**On slide (vertical flow)**
```
Feature → Manual tracking → QA → Release → Analytics finds breaks → Manual fix
```

**Bullets**
- Silent breakage across releases  
- Manual catalogue maintenance  
- Unreliable funnels & product decisions  
- Extra load on Dev + QA + Data  

---

## Slide 4 — The shift

**Title:** Move validation before merge

**On slide (side-by-side)**
| Before | After |
|--------|--------|
| Fix in production | Fail in CI |
| Tribal event names | Shared Event Contract |
| Manual reviews | Automated governance |

**One line:** AI proposes standards; rules enforce them.

---

## Slide 5 — Solution overview

**Title:** AI-powered quality gate for analytics events

**On slide (simple architecture)**
```
PRD / Jira → AI Analyzer → Event Catalogue (contracts)
                              ↓
                     Code Validator → CI PASS/FAIL
```

**Four AI jobs (icons or short list)**
1. Discover actions  
2. Standardize / reuse  
3. Generate contract  
4. Explain validation failures  

---

## Slide 6 — Heart of the system: Event Contract

**Title:** Events as versioned contracts (like APIs)

**On slide**
- Show `purchase_button_clicked` JSON (name, platforms, params, types, required, version, status)
- Badge: ACTIVE / DEPRECATED

**Speaker note:** This is the single source of truth everything else hangs on.

---

## Slide 7 — AI + rules (credibility)

**Title:** Hybrid by design

**On slide (two columns)**
| AI | Deterministic rules |
|----|---------------------|
| Understand PRDs | Required fields |
| Suggest events | Data types |
| Semantic duplicates | Naming conventions |
| Explain failures | CI pass/fail |

**One line:** LLMs for meaning; validators for merge gates.

---

## Slide 8 — Live demo setup

**Title:** Demo: Buy Now for Broadband

**On slide**
- Jira/PRD snippet (2–3 lines)
- Expected outcomes: `plan_selected` · `purchase_button_clicked` · `checkout_started`
- Note: intentionally broken PR next

**Speaker note:** Transition to live UI / terminal. Do not stay on slides during the wow moment.

---

## Slide 9 — Demo beats (or live only)

**Title:** End-to-end in one journey

**If you need a backup slide when live demo fails, put screenshots here:**
1. AI reuse suggestion (similarity %)  
2. Contract detail  
3. CI FAIL on `buy_now` + wrong types  
4. CI PASS on corrected `purchase_button_clicked`  
5. Catalogue entry  

**Speaker note:** Prefer live; this slide is contingency.

---

## Slide 10 — MVP & team

**Title:** What we built (and who owns what)

**On slide**
- 5 MVP features: generate · catalogue · contracts · validate · CI  
- Team: P1 AI/Backend · P2 Validator/CI · P3 UI/Demo  
- Explicit non-goals (small footer): no custom LLM, no Kafka, no auto-prod code rewrite  

---

## Slide 11 — Impact & metrics

**Title:** How we measure success

**On slide**
- Consistency: 5 names → 1 standard event  
- Pre-merge issues caught (prototype count from demo)  
- Duplicates suggested, not auto-deleted  
- Review time: minutes → seconds  

**Footer:** Prototype measurements from Vibeathon demo

---

## Slide 12 — Roadmap & ask

**Title:** Next: governance that scales

**On slide**
```
MVP → Jira/GitHub + multi-lang → Runtime monitoring → Semi-autonomous PRs
```

**Close**
- Ask: pilot on one product line (e.g. Broadband + Shop)  
- Closing line: *Stop fixing analytics after production. Validate events before they ship.*

---

## Optional backup slides (appendix)

| # | Title | Use if asked |
|---|--------|--------------|
| A1 | Sample validation report JSON | Deep technical |
| A2 | LangGraph / RAG flow | Architecture curiosity |
| A3 | Platform allow-list rules | Multi-platform question |
| A4 | Versioning & deprecation | Data governance question |
| A5 | Threats & mitigations (LLM hallucination → structured JSON + rules) | Risk question |

---

## Demo script (aligned to slides 8–9)

| Minute | Action | Say |
|--------|--------|-----|
| 0:00–1:00 | Slide 2–3 | Contract drift across 5 platforms |
| 1:00–2:00 | Live: paste PRD | AI discovers + recommends reuse |
| 2:00–3:00 | Live: open contract | Show required params/types |
| 3:00–4:00 | Live: bad PR / CI | FAIL with concrete issues |
| 4:00–5:00 | Live: fix → PASS + catalogue | Close with tagline |

**Practice rule:** One happy path only. No feature tour.

---

## Visual guidelines for slides

- One idea per slide  
- Prefer the architecture diagram from the README (single column flow)  
- Avoid purple-glow “AI aesthetic”; keep brand-neutral and readable  
- Use red ❌ / green ✅ only on validation slides  
- Font size large enough for a room projector  

---

## Suggested slide titles (copy-paste deck)

1. Event Governance Engine  
2. Analytics contract drift  
3. Problems found after release  
4. Validate before merge  
5. Solution overview  
6. Event Contract  
7. AI + rules hybrid  
8. Demo scenario  
9. Demo results (backup)  
10. MVP & team  
11. Success metrics  
12. Roadmap & close  
