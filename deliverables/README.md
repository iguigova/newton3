# Newton 3 — Overview

Newton 3 is a behaviour-driven allocation engine for shared workplace resources —
parking, desks, EV chargers. Here is where each part of the project lives.

## ▶ Start here — the live demo

**[`demo.html`](demo.html) is the single best way to see Newton 3.** Open it in any browser
(no install): a scrollable page whose centerpiece is **the actual scoring engine running in
your browser** — a faithful port of [`newton/engine.py`](../src/newton/engine.py). Add
events, drag them through time, and watch the score and its reconciling trace recompute
live. The same page carries verbatim API request/response, the two mandatory proposals
(#1 offence override, #8 explainability), the 1,200-user impact audit, and the composed ML
stretch — the whole project in one self-contained file.

| Material | Where |
|---|---|
| **Live demo** ⭐ | [`demo.html`](demo.html) — the engine, running in your browser; no install. |
| **Demo (decks)** | [`slides.html`](slides.html) (pitch deck) · [`walkthrough.html`](walkthrough.html) (real command output, narrated) · [`DEMO.md`](DEMO.md) (beats + the commands). |
| **Documentation** | [`docs/README.md`](../docs/README.md) (source of truth) · [`src/newton/README.md`](../src/newton/README.md) (how the prototype works). |
| **Architecture / technical overview** | [`ARCHITECTURE.md`](ARCHITECTURE.md). |
| **Supporting materials** | [`INSIGHTS.md`](INSIGHTS.md) (insights + future improvements) · [`analysis/REPORT.md`](../analysis/REPORT.md) (data audit). |

## The one-paragraph pitch

Newton 3 reframes the behaviour score as a **pure fold over an append-only event log** —
`score(events, config, now)` — instead of stored state. Persistence, per-event decay,
explainability, and per-tenant configurability stop being features to build and become
**properties of that one function**; the weekly decay job is deleted outright (decay is
computed at read time). Every score and allocation outcome carries its own reconciling
reason (GDPR Art. 22). It ships a **runnable, curl-able read API** (standard library only)
and an **ML stretch** — a predictive no-show model that sizes overbooking while staying
*out* of the score, so the ranking stays explainable. On the synthetic 1,200-user dataset the
*documented defaults barely move any score* — a genuine finding, and the case for
tenant-configurable windows. Tune the memory to the data and the same engine cleanly
separates genuine abuse (tiers M, X sink) from the high-demand underserved (A, B, C stay
near base); a shadow comparator shows exactly whom it reorders before any cut-over.

## What the project shows

| Theme | Evidence |
|---|---|
| **Innovation & creativity** | Score-as-a-fold makes persistence, decay, explainability and config properties of one pure function; the weekly decay Lambda disappears. A composed ML stretch (predictive no-show → overbooking) never touches the explainable score. |
| **Business impact** | [`analysis/REPORT.md`](../analysis/REPORT.md): targets abusers, protects the underserved. |
| **Technical quality** | Pure, clock-injected engine; 63 tests (incl. data invariants); ruff-clean; idempotent under at-least-once delivery; structured audit logging; config-versioned, reproducible responses. |
| **Scalability & maintainability** | Decay windows bound the fold; log is compactable; `Config` is the only policy surface; DynamoDB swaps in behind the store Protocol. |
| **Alignment** | Implements the behaviour-scoring spec faithfully, plus the complaint-analysis proposals #1 (offence override) and #8 (explainable outcomes). |
| **Demonstration & execution** | [`DEMO.md`](DEMO.md) — runnable commands (tests, live API, data audit, ML), one narrative; two browser decks. |

## Honesty ledger

What is **not** claimed:

- The audit reconstructs events from 3-month aggregates (method + caveat in
  `analysis/impact.py`); it models recent standing, not lifetime totals.
- Under the documented default windows the score barely moves on this data — a real
  finding, and the argument for tenant-configurable windows. The report shows both
  defaults and a long-memory profile.
- A *stored* ranked GSI drifts stale between writes; the prototype recomputes at read.
  Production needs the snapshot + `next-change-at` refresh described in
  [`ARCHITECTURE.md`](ARCHITECTURE.md).
- The ML stretch (`analysis/predict.py`) is a dependency-free baseline trained on the same
  reconstructed aggregates; with a real event log it would retrain on actual outcomes. It
  feeds *capacity*, never the score.
- Open design questions (cap vs Platinum, score scope, allocation cadence) remain to be
  settled — listed in [`docs/README.md`](../docs/README.md#open-questions).
