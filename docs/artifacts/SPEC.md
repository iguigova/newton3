# Newton — Design Specification

A self-contained spec for **Newton**, a behaviour-driven allocation engine for shared
workplace resources (parking spaces, desks, EV chargers). It consolidates three concerns:
the allocation redesign, the behaviour-scoring model, and the technical design. Everything
here is original and generic — no customer or production system is described.

This spec is the design reference the rest of the repository implements. The prototype in
[`src/newton`](../../src/newton) is the faithful, runnable version of it.

---

## 1. Problem

A legacy, rule-based allocator decides who gets a space when demand exceeds supply. Its
ranking logic is opaque: users cannot see why they were rejected, the rules are hard to
explain, and there is no behavioural incentive to release unused capacity. The recurring
complaints are *"allocation feels random"*, *"I never get the days I ask for and nobody
tells me why"*, and *"I was penalised for a no-show I didn't commit."*

Newton replaces that with a **transparent, fair, behaviour-aware** ranking that stays
explainable end to end.

## 2. Allocation model

Priority is applied in layers. Newton adds a system-controlled behaviour score as a new
third layer on top of the existing admin-controlled priorities:

```python
def allocation_sort(user):
    return (
        user.group_priority,    # Layer 1 — admin-controlled group priority
        user.user_priority,     # Layer 2 — admin override
        -user.behavior_score,   # Layer 3 — system-controlled behaviour (NEW)
        random(),               # Layer 4 — tie-break
    )
```

Behaviour only ever reorders users **within** an identical admin-priority bracket — exactly
where the legacy system fell back to a random tie-break. It never overrides an admin
decision.

## 3. Behaviour-scoring model

Each user starts at `base_score = 100`. An append-only **event log** records what they do;
the score is a pure function of that log evaluated at read time.

| Event | Points | Window |
|---|---|---|
| Unused booking (no-show) | **-3** | allocation cycle |
| Free / non-paid space usage | **-1** | 2 weeks |
| Offence (rule violation) | **-5** | 4 weeks |
| Carpool participation | **+5** | — |
| Decay (recovery) | **+2 / week** since last penalty | up to base 100 |
| Reward cap | **+20 max** | rolling 4 weeks (anti-gaming) |
| Floor | `max(score, 0)` | hard minimum |

Scores map to user-facing tiers: Platinum 150+, Gold 120–149, Silver 80–119, Bronze 50–79,
Restricted <50.

### Design rules

- **Scores are persistent and event-sourced**, never reset per allocation cycle.
- **Decay is per-event and linear** over a configurable window; each penalty fades on its
  own timer rather than on a single global one. Repeat penalties of the same type may
  **escalate** by tenant policy (off by default).
- **All policy lives in a per-tenant config** — point values, windows, cap, escalation,
  tier thresholds, and which events are enabled. Defaults reproduce this spec; a tenant is
  a different config.
- **The clock is injected.** Decay is computed at read time, so a score is always current
  with no scheduled recompute job.

## 4. Mandatory & high-value behaviours

| Tier | # | Proposal | Mechanism |
|---|---|---|---|
| Mandatory | #1 | Threshold-based offence override | N offences in 30 days → forced lowest priority, regardless of admin settings |
| Mandatory | #3 | Customer priority feed API | Accepts a weekly JSON priority list owned by the tenant's transport/HR team |
| Mandatory | #8 | Native explainability surface | Every rejection includes a structured rationale (your rank, the bracket above you, a better-odds alternative date) |
| High-value | #2 | Approval-rate parity | 30-day approval rate vs office median → priority bump if below, dip if above |
| High-value | #4 | Real-time capacity transparency | Show estimated chance at request time; suggest alternate dates |
| High-value | #5 | Explicit waitlist | Rejected → ranked waitlist with a visible position and auto-promotion on releases |
| Stretch | #6 | Self-declared priority days | N tokens per quarter weight a request more heavily |
| Stretch | #7 | Cancellation/release credits | Releasing early earns a small priority credit |

## 5. Technical design

Serverless, event-driven, multi-region. A legacy service remains source-of-truth only
during a shadow-mode migration:

```
Legacy service (source-only) ─► Migration Script ─► AWS Isolated Stack (Newton vNext)

  EventBridge Bus ─┬─► Scoring Lambda      (read/write score, append event)
                   ├─► Decay Lambda         (weekly EventBridge schedule, optional)
  Newton run      ─┼─► Allocation Lambda    (fetch score + tenant config, sort, emit)
  Identity API    ─┴─► API Lambda           (GET /users/{id}/behavior-score)

  DynamoDB: behavior-score · behavior-events · tenant-config
  Global Tables → EU eu-west-1 + US us-west-1
                   │
                   ▼  Shadow-mode Comparator (parity vs legacy output)
```

### Data model

- `behavior-score` — keyed `USER#id` (optionally scoped `GROUP#id`), the materialised
  current score plus a `next-change-at` timestamp for lazy refresh.
- `behavior-events` — keyed `USER#id / EVENT#ts`, the append-only log.
- `tenant-config` — keyed by tenant, all policy values.

Descending-score ranking within a group uses a GSI keyed `GSI1-PK = GROUP#id`,
`GSI1-SK = SCORE#<zero-padded-inverted-score>`, so a single query returns the group
ranked best-first. The prototype's `gsi_sort_key()` packs exactly that key.

### Migration

Shadow mode runs Newton alongside the legacy allocator and diffs the two rankings within
each admin-priority bracket (behaviour is the only thing Newton adds, so a pooled diff
would overstate movement). The legacy scheduler fires allocation runs periodically; on AWS
the equivalent is an EventBridge schedule, with care taken that queue redelivery cannot
double-fire a run.

## 6. Open questions

1. **Reward cap vs Platinum tier** — the +20/4-week cap makes Platinum (150+) unreachable
   from base 100. Deliberate aspirational tier, or raise the cap?
2. **Free-space penalty** — keep with a stated rationale, or drop? Penalising sanctioned
   behaviour erodes trust unless explained.
3. **Allocation cadence** — daily batch, on-demand, or per-request? It constrains the rest
   of the design.
4. **Score scope** — per-user or per-(user, group)?
5. **Approval-rate parity (#2)** — a fourth scoring input, or a replacement for score-based
   ranking?
