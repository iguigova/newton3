# Newton — Design Specification (v2)

A behaviour-aware allocation engine for shared workplace resources — parking, desks, EV
chargers — when demand exceeds supply. This revision reorganises the design around the
objective it serves and the metrics that measure it. The behaviour score is retained as a
small optional layer; the product is transparency, fair rationing, and capacity recovery.

This supersedes [`artifacts/SPEC.md`](./artifacts/SPEC.md). The reasoning behind the change
is in [`REEVALUATION.md`](./REEVALUATION.md).

---

## 1. Objective & success metrics

Newton ranks users for a scarce resource and explains the result. Success is measured, not
asserted. Every feature in this spec maps to one of these metrics; a feature that maps to
none is cut.

| Goal | Metric | Target |
|---|---|---|
| **Transparent** | Share of allocation decisions (grant *and* reject) carrying a machine-readable rationale | 100% |
| **Fair** | Approval-rate gap between the worst-served decile and the office median | Shrinks cycle over cycle |
| **Correct** | Penalty events later overturned on appeal | ≈ 0% |
| **Less scarce** | Effective fill rate via overbooking, with no rise in same-day turn-aways | Fill rate up, turn-aways flat |
| **Predictable** | Share of repeat requesters who can see their odds *before* requesting | 100% |

## 2. Allocation model

Priority is applied in layers. Layers 1–2 are admin-controlled and unchanged. The fairness
correction (Layer 3) is the primary system contribution; the behaviour score (Layer 4) is
an optional nudge, off by default.

```python
def allocation_sort(user, cfg):
    return (
        user.group_priority,                 # Layer 1 — admin-controlled group
        user.user_priority,                  # Layer 2 — admin override
        parity_rank(user, cfg),              # Layer 3 — approval-rate parity (fairness)
        -user.behavior_score if cfg.behaviour_enabled else 0,  # Layer 4 — optional nudge
        stable_tiebreak(user),               # Layer 5 — deterministic, seeded (not random)
    )
```

- **Layer 3 — approval-rate parity (proposal #2).** Within an equal-priority bracket, a
  user whose 30-day approval rate sits below the office median is bumped up; one above is
  eased down. This is what moves outcomes for the underserved high-demand population, and
  it is the fairness metric in §1 made operational. It is a ranking input, not a behaviour
  score.
- **Layer 4 — behaviour score.** A per-user score retained from v1, now optional and
  off by default. When a tenant enables it, it breaks ties *after* the parity correction.
  It never overrides an admin decision and never overrides fairness.
- **Layer 5 — deterministic tie-break.** Replaces the legacy random fallback with a stable
  seeded order, so an unexplained "random" outcome never reaches a user.

## 3. The product: what actually answers the complaints

These are core deliverables, not stretch goals. Each maps to a complaint and a metric.

| Capability | Proposal | Answers | Metric |
|---|---|---|---|
| **Explainability on every decision** | #8 | *"nobody tells me why"* | Transparency = 100% |
| **Capacity transparency at request time** | #4 | *"I never get Tuesdays"* | Predictable = 100% |
| **Waitlist with visible position + auto-promotion** | #5 | rejection feels final | Predictable; fill rate |
| **No-show prediction → overbooking** | (built) | scarcity | Fill rate up, turn-aways flat |
| **Release credits for early cancellation** | #7 | hoarding / "release at 3pm" | Fill rate up |
| **Customer priority feed** | #3 | admin overrides done by hand | (operational) |

- **Explainability (#8).** Every grant and rejection carries a structured rationale: the
  user's rank, the bracket above them, the deciding factor, and a better-odds alternative
  date. The prototype's `decide()` already attaches this; it is promoted to a contract —
  no decision ships without one.
- **Capacity transparency (#4).** At request time the user sees the estimated chance for
  each day ("Tuesday: 47 requests / 80 spots — your est. chance 35%") and a suggested
  better day. This pre-empts the rejection rather than explaining it after the fact.
- **Waitlist (#5).** A rejection enters a ranked waitlist with a visible position and
  auto-promotes on releases. Rejection becomes a queue, not a dead end.
- **Overbooking from no-show prediction.** `analysis/predict.py` already turns predicted
  attendance into an overbooking factor. It feeds **capacity, never ranking**, so no model
  decides who gets a space — it only decides how many spaces to offer.
- **Release credits (#7).** Releasing a booking well before the cycle earns a small
  priority credit, recycling capacity while it is still reusable.

## 4. Behaviour score (optional layer)

Retained, simplified, and demoted. A tenant may enable it; it ships off.

- **Pure read-time fold.** `score(events, config, now)` over an append-only event log.
  Persistence, decay, and explainability are properties of the fold, not subsystems.
- **Persistent, never reset.** The score is event-sourced and always current.
- **Per-event linear decay** over a configurable window; each penalty fades on its own
  timer. Optional escalation for repeat same-type penalties, off by default.
- **All policy is per-tenant config** — point values, windows, decay rate, which events
  are enabled, and whether the layer is on at all. Defaults reproduce this spec.
- **No tier ladder.** Platinum/Gold/Silver/Bronze/Restricted are removed: gamifying a work
  necessity carries equity and HR risk for no measured benefit, and the tiers contradicted
  the reward cap. Any user-facing label is derived from approval outcomes, not the score.
- **Dropped signals.** The free-space `-1` penalty is removed — penalising sanctioned
  behaviour erodes trust.

## 5. Penalties: accuracy before enforcement

The rule that answers complaint #3:

- A noisy detector (e.g. ANPR no-show detection) **may inform capacity** (a soft
  prediction signal) but **may not feed a persistent person-penalty** until its accuracy is
  demonstrated against ground truth.
- Every penalty is **decaying** and **contestable** — a user can appeal, and overturned
  penalties are erased from the fold. The appeal-overturn rate is the §1 correctness
  metric.
- The threshold-based offence override (#1) is retained but enforced **only behind a proven
  detector**; threshold and window are tenant-configurable.

## 6. Architecture

Right-sized to the real load: an office-sized population allocated on a schedule. The
computation is a pure fold over an event log.

```
Booking / gate / offence events ─► Event log (append-only)
                                        │
                                        ▼
   Allocation run (per cycle) ─► score() fold + parity + overbooking ─► ranked grant/reject
                                        │                                      │
                                        ▼                                      ▼
                              Read API (GET /users/{id}/behavior-score)   Explanation + waitlist
```

- **One store** behind an `EventStore` interface. `InMemoryStore` for the prototype;
  `DynamoEventStore` is a drop-in swap with no change above the store.
- **No scheduled decay job** — decay is computed at read time.
- **Defer** the EventBridge bus, the Lambda fleet, and multi-region Global Tables until a
  real load justifies them. Single-region, single-store is the starting point.
- **Shadow mode** diffs Newton's ranking against the legacy allocator *within each
  admin-priority bracket* (behaviour and parity only reorder inside a bracket). Cut-over is
  gated on the divergence review.

## 7. What changed from v1

| v1 | v2 |
|---|---|
| Behaviour score is the headline | Behaviour score is an optional, off-by-default tie-breaker |
| No objective or metrics | §1 objective + five measured targets |
| Approval-rate parity is an open question | Parity is the primary within-bracket fairness layer |
| Tier ladder (Platinum…Restricted) | Removed |
| Free-space `-1` penalty | Removed |
| Random tie-break | Deterministic seeded tie-break |
| Noisy detector feeds persistent penalty | Soft signal informs capacity; penalties proven, decaying, contestable |
| Explainability / capacity / waitlist are nice-to-have | Core deliverables with metrics |
| Multi-region serverless fleet | Single-region pure fold + one store; scale deferred |
| Eleven open questions | Resolved in [`REEVALUATION.md`](./REEVALUATION.md) |
