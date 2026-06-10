# Newton 3 — Prototype

This package is the Newton 3 prototype. It is the design from
[`docs/README.md § Design decisions`](../../docs/README.md#design-decisions--critique)
reduced to its core: **the behaviour score is a pure fold over an append-only event
log.**

## The idea

```
score(events, config, now) = max(floor, base + min(rewards, cap) + penalties)
```

A deterministic function of `(events, config, now)`. There is no stored score to reset
and no decay job to run. Decay is computed at read time; each event fades linearly across
its own window and then drops out.

## What the fold dissolves

| Reviewed gap | Why it disappears |
|---|---|
| Persistent vs. ephemeral scores | Score is always derived from the log — nothing to reset. |
| Per-event decay, not a global timer | Each event decays against its own timestamp inside the fold. |
| Explainability / GDPR Art. 22 | The fold's per-event contributions *are* the "recent impacts" view. |
| Hardcoded weights | `Config` is a parameter; per-tenant = a different `Config`. |
| Weekly Decay Lambda | Deleted — decay is read-time, so scores are current to the query. |

## Bounded by construction

An event older than its window contributes exactly zero, so the fold only ever touches a
recent slice and `InMemoryStore.compact()` can drop the rest. Score is O(recent events)
per user — the log does not grow with history.

## Modules

| File | Role |
|---|---|
| `models.py` | Immutable value objects (`Event`, `Impact`, `Breakdown`, `Candidate`, enums). |
| `config.py` | Per-tenant policy: weights, windows, cap, escalation, tiers, enabled events. |
| `engine.py` | The fold: `evaluate` / `score` / `tier`. Pure, no I/O, clock injected. |
| `allocate.py` | `rank` (3-layer sort) and `gsi_sort_key` (the inverted-score DynamoDB key). |
| `store.py` | `EventStore` Protocol + `InMemoryStore`; DynamoDB swaps in unchanged. |
| `api.py` | `GET /users/{id}/behavior-score` → score + impact trace (framework-free). |
| `app.py` | A runnable stdlib HTTP shell around `api.py` — `curl`-able, zero deps. |
| `cli.py` | Event-stream simulator; the only clock reader. |

## Design choices, stated normatively

- **Scores are persistent and event-sourced**, never reset per cycle.
- **Decay is per-event and linear** over a configurable window; repeat penalties of one
  type may **escalate** (`Config.escalation`, default off — spec-faithful).
- **The clock is injected**: `now` is an argument everywhere, so the engine is pure and
  tests are plain input→output with no mocks.
- **`Config` carries all policy.** Defaults reproduce the documented spec; an event
  absent from `Config.weights` is disabled.

## The one tradeoff

A *stored* ranked GSI drifts stale between writes, because a score changes with time even
with no new events (decay/expiry). The prototype **recomputes at read** (correct, and
fine well past prototype scale). Production materialises a snapshot plus a
`next-change-at` timestamp for lazy refresh; `gsi_sort_key()` is the packed key it would
store.

## Run

From the repository root:

```bash
pytest                       # 63 tests, no external deps
python -m newton.cli demo    # event stream → ranking + a behaviour-score response
python -m newton.app         # serve the read API on :8000 (stdlib only)
curl -s localhost:8000/users/bob/behavior-score   # → live score + impact trace
```
