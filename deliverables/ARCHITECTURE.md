# Newton 3 — Architecture / Technical Overview

## The core decision

The behaviour score is **not stored, mutated state**. It is a pure function of an
append-only event log evaluated at a point in time:

```
score(events, config, now) = max(floor, base + min(rewards, cap) + penalties)
```

Everything else is a thin shell around that one function. This is the decision that
settles the review's "TDD vs Behaviour Scoring page contradict on persistence" issue:
scores are **event-sourced and continuously derived**, never reset per cycle.

## What the reframing delivers

| Requirement | How the fold delivers it |
|---|---|
| Always-current score | Always derived from the log — nothing to reset, never stale. |
| Fair, per-event decay | Each event decays against its own timestamp, inside the fold. |
| Explainability (GDPR Art. 22) | The fold's per-event contributions *are* the explanation; arithmetic reconciles to the score by construction. |
| Per-tenant policy | `Config` is a parameter; per-tenant = a different `Config`. |
| Fewer moving parts | The weekly decay Lambda is gone — decay is computed at read time, so scores are correct to the query. |

## How it runs without AWS

AWS is only the *deployment target*, never a *dependency*. The prototype runs on the
Python standard library alone — `pytest` and `python -m newton.cli demo` need nothing
installed. That is possible because of four deliberate choices:

| What AWS would provide | How the prototype runs without it | Why no dependency |
|---|---|---|
| **DynamoDB** (score / event tables) | `InMemoryStore` behind the `EventStore` Protocol (`store.py`) | The score is derived from events, so storage is just a list; a DynamoDB-backed class implementing the same Protocol swaps in with zero changes above it. |
| **Lambda** (compute) | Plain functions — `engine.evaluate`, `allocate.rank` | The brain is a pure function. A Lambda handler is a 3-line shell that calls it. Identical code locally and in AWS. |
| **EventBridge** (event bus) | `cli.py` feeds events from a list / `InMemoryStore.extend` | Nothing in the engine cares *how* an event arrived. |
| **EventBridge Scheduler** (the weekly decay job) | Nothing — it is deleted | Decay is computed at read time from `now`, which is injected as an argument. No clock, no cron, no scheduler. |

So the rule is the brief's own: *"design as if DynamoDB is the target; run in-memory
locally."* Going to AWS later is wrapping the same `engine.evaluate` in Lambda handlers
and writing one `DynamoEventStore(EventStore)` — the pure core never changes, which is
also why the tests need no mocks.

## Target AWS topology

The legacy service stays source-of-truth only during a shadow-mode migration:

```
Legacy service (legacy) ─► Migration Script ─► AWS Isolated Stack (Newton vNext)

  EventBridge Bus ─► Scoring path     (append event; no score write needed)
  Newton run      ─► Allocation Lambda (fold candidates, sort, emit winners)
  Identity API    ─► API Lambda        (GET /users/{id}/behavior-score + trace)
  DynamoDB: behavior-events · tenant-config   (behavior-score becomes a cache,
                                               not the source of truth)
  Global Tables → EU eu-west-1 + US us-west-1
                   │
                   ▼  Shadow Comparator (parity vs legacy ranking)
```

Note: with decay at read time there is **no Decay Lambda and no EventBridge decay
schedule** — one fewer moving part, and no "scores stale between runs" window.

## Prototype → production mapping

The prototype (`src/newton/`) is the Lambda *logic*; the shells are trivial.

| Module | Production role |
|---|---|
| `engine.py` | Body of the Scoring/Allocation Lambdas — pure, so identical locally and in AWS. |
| `config.py` | A `tenant-config` DynamoDB item, loaded per request. |
| `store.py` (`EventStore` Protocol) | `behavior-events` table; `InMemoryStore` swaps for a DynamoDB-backed impl with no change above it. |
| `allocate.py` | Allocation Lambda sort; `gsi_sort_key()` GSI key; `decide()` per-user outcomes with rationale (#8); the offence override (#1). |
| `api.py` | API Lambda handler for `GET /users/{id}/behavior-score`. |
| `app.py` | A stdlib HTTP shell that serves `api.py` locally (`curl`-able); in AWS this is API Gateway + Lambda, wrapping the *same* functions. |

Shadow-mode comparison lives in `analysis/shadow.py`. Its `legacy_rank` mocks the legacy
allocator; in production the comparator diffs the new ranking against real legacy output,
using the same position comparison.

## Data model — the GSI

DynamoDB sort keys are ascending only, so a numeric score sorts worst-first. Invert and
zero-pad it so ascending lexical order equals best-first, and one `Query` returns a group
already ranked:

```
GSI1-PK = GROUP#<id>
GSI1-SK = <group_priority>#<user_priority>#<9999 - score>   (zero-padded)
```

`allocate.gsi_sort_key()` produces exactly this key.

## Bounded by construction

An event older than its window contributes exactly zero, so the fold only ever reads a
recent slice and `InMemoryStore.compact()` (a DynamoDB TTL in production) drops the rest.
Score cost is O(recent events) per user; the log does not grow with history.

## The one tradeoff, stated plainly

A *materialised* ranked GSI drifts stale between writes, because a score changes with time
even with no new event (decay, expiry). Two correct stances:

- **Prototype / moderate scale:** recompute at read (fold the bounded window per
  candidate). Always correct; no background jobs.
- **High scale:** store a score snapshot plus a `next-change-at` timestamp and refresh
  lazily on read or via a cheap sweep. The GSI key above is what you'd persist.

## Idempotency, audit, and traceability

- **Idempotency.** Each `Event` carries an optional `event_id`. Under at-least-once
  delivery (EventBridge, SQS) a redelivered event repeats its id, and the fold counts it
  once — the double-fire the legacy scheduler warned about cannot occur.
- **Audit log.** `observability.log_evaluation` and `log_allocation` emit structured
  records (user, score, tier, `config_version`, timestamp) under the `newton` logger; the
  application owns routing. The pure engine emits no logs.
- **Traceability.** Every score response carries `config_version` and `evaluated_at`, so a
  decision reproduces exactly from `(events, config_version, evaluated_at)`.

## Configurability surface

`Config` is the entire policy surface and is validated on construction: point values,
decay windows, reward cap, escalation factor, tier thresholds, and which events are
enabled (an event absent from `weights` is off). Defaults reproduce the documented spec.
