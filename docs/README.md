# Newton 3 — Specification, Analysis & Design

This is the **single source of truth** for Newton 3: what it is, the source materials it
was built from, the data behind it, and the normative design decisions, critique, and
open questions that shape the implementation.

The source files referenced here sit in [`artifacts/`](./artifacts).

> **Re-evaluation (2026-06):** after building the prototype, the design was re-read
> against the goal it serves. The behaviour score is demoted to an optional layer; the
> product is transparency, fair rationing, and capacity recovery. See
> [`REEVALUATION.md`](./REEVALUATION.md) for the critique and the decision taken on every
> open question, and [`SPEC.v2.md`](./SPEC.v2.md) for the redesigned spec that supersedes
> [`artifacts/SPEC.md`](./artifacts/SPEC.md).

---

## Source artifacts

The source materials are listed below.

| File | Origin |
|---|---|
| `SPEC.md` | Consolidated design spec — the allocation engine redesign, behaviour scoring system, and technical design, in one document |
| `CLAUDE.md` | AI-pair-programming brief |
| `generate_synthetic_data.py` | Seeded generator that produces the four CSVs below |
| `Algorithm User Complaints - Read Me.csv` | Methodology notes + proposal legend |
| `Algorithm User Complaints - Support Tickets.csv` | ~40 synthetic support threads tagged to proposals |
| `Algorithm User Complaints - NPS Responses.csv` | ~320 synthetic NPS verbatims tagged with Underserved Tier + Verbatim Quality |
| `Algorithm User Complaints - Metabase.csv` | ~1,200 synthetic users with objective metrics + Underserved Tier |

The four CSVs are **synthetic**: they are generated deterministically by
`generate_synthetic_data.py` (a single seed produces ~1,200 example users with stable
identities, objective metrics, tiers, and proposal tags). They are not a real or
anonymized export — they exist so the engine can be exercised end-to-end against a
realistic-looking dataset.

---

## What Newton 3 is

A **behaviour-driven allocation system** that replaces a legacy rule-based
prioritization. It introduces a per-user `behavior_score` (starts at 100) as a
**third-layer priority signal** added to the existing two-layer model:

```python
def allocation_sort(user):
    return (
        user.group_priority,        # Layer 1 — admin-controlled (existing)
        user.user_priority,         # Layer 2 — admin-controlled (existing)
        -user.behavior_score,       # Layer 3 — system-controlled (NEW)
        random()                    # Tie-breaker
    )
```

That's it. The "AI-driven" framing in the spec is really a **deterministic rules +
decay scoring system**, not ML. The spec's "Future Evolution" section lists "ML-based
scoring" and "Dynamic weights" as Phase 5+, not Phase 1.

### Scoring rules (concrete)

| Event | Points | Window |
|---|---|---|
| Unused booking (no-show) | **-3** | Allocation cycle |
| Non-paid / free space usage | **-1** | 2 weeks |
| Offence (rule violation) | **-5** | 4 weeks |
| Carpool participation | **+5** | — |
| Decay (recovery) | **+2/week** | up to base 100 |
| Reward cap | **+20 max** rolling 4 weeks | (anti-gaming) |
| Floor | `max(score, 0)` | hard min |

### Tier mapping (UX surface)

| Tier | Range |
|---|---|
| Platinum | 150+ |
| Gold | 120–149 |
| Silver | 80–119 |
| Bronze | 50–79 |
| Restricted | <50 |

> Note: the +20/4wks reward cap means Platinum (150+) is **unreachable** from base 100
> under the documented mechanics — see [Scoring model § asymmetric caps](#15-asymmetric-caps)
> and [Open questions](#open-questions).

### Target AWS architecture (from the spec)

```
Legacy service (source-only)
    │
    ▼
Migration Script (idempotent, auditable, incremental)
    │
    ▼
┌─────────────────────────────────────────────────┐
│ AWS Isolated Stack (Newton vNext)               │
│                                                 │
│  EventBridge Bus ─┬─► Scoring Lambda            │
│  (booking.* /     │   ├── read/write score      │
│   gate.entry /    │   └── append event          │
│   offence /       │                             │
│   carpool)        │                             │
│                   │                             │
│  EventBridge      ├─► Decay Lambda (weekly)     │
│  Schedule         │                             │
│                                                 │
│  Newton           ─► Allocation Lambda          │
│                       ├── fetch score           │
│                       ├── fetch tenant config   │
│                       └── sort + emit winners   │
│                                                 │
│  Identity API ───► API Lambda                   │
│                    └── GET /users/{id}/         │
│                          behavior-score         │
│                                                 │
│  DynamoDB:                                      │
│    behavior-score   (USER#id / GROUP#id)        │
│    behavior-events  (USER#id / EVENT#ts)        │
│    tenant-config    (base/weights/caps/flags)   │
│                                                 │
│  Global Tables → EU eu-west-1 + US us-west-1    │
└─────────────────────────────────────────────────┘
                    │
                    ▼
            Shadow-mode Comparator
            (parity vs Legacy output)
```

---

## File-by-file read

### 1. `CLAUDE.md` — the AI-pair-programming brief

This is **a CLAUDE.md written for AI assistants** — not a normal project CLAUDE.md. Key
directives:

- **Implementation language is Python** (more specific than the spec's "AWS-native
  architecture and AI-driven approaches" wording — the spec leaves it open, the CLAUDE.md
  fixes it).
- Explicit *non-goal*: **"You do NOT need to understand the legacy rule-based service in
  depth."** The project does not require porting — it requires building from spec.
- Suggested module skeleton: `scoring_engine.py`, `allocation_engine.py`,
  `event_processor.py`, `models.py`, `api.py`, `cli.py`, `tests/`.
- Local prototype OK: "in-memory dict / SQLite for local prototype, design as if
  DynamoDB is the target."
- Three deliverable tiers: **Must have** (event processing, decay, reward cap, ranking),
  **Nice to have** (REST endpoint, explainability, shadow mode), **Innovative/AI-driven**
  (LLM-assisted explanation, ML anomaly detection, dynamic per-tenant weights, predictive
  no-show).
- Resolves the spec's "AI-driven" ambiguity: it lists AI as a **stretch goal**, not a
  **must-have** — so AI is the differentiator, not the floor.
- Slight numeric discrepancy with the spec: the CLAUDE.md's example
  `decay = min(weeks_since_last_penalty * 2, base_score - current_score)` caps recovery
  at base 100, while the spec's tier table places Platinum at 150+. This is the same
  internal inconsistency the spec carries — confirming it's a design open question, not
  just a documentation slip.

### 2. `Read Me.csv` — the analytical scaffold

| Tier | Proposal # | Mechanism (one-liner) |
|---|---|---|
| **MANDATORY** | #1 | **Threshold-based offence override** — N offences in 30d → forced step-1 priority = 0 (bypasses Newton 2's tie-resolution gating) |
| **MANDATORY** | #3 | **Customer Priority Feed API** — Public endpoint accepts weekly JSON priority list from customer transport/HR (productises an existing customer priority-feed model) |
| **MANDATORY** | #8 | **Native explainability surface** — Every rejection includes structured rationale (your rank, higher-priority bracket, suggested alternative date with higher chance) |
| HIGH-VALUE | #2 | **Approval-rate parity** — Each user's 30-day approval vs office median → bump if below, dip if above (replaces step-4 history count) |
| HIGH-VALUE | #4 | **Real-time capacity transparency at booking** — Show "Tuesday: 47 reqs / 80 spots — your est. chance 85%" at request time |
| HIGH-VALUE | #5 | **Explicit waitlist mechanism** — Rejected = auto-joins ranked waitlist with visible position + auto-promotion + push notify |
| STRETCH | #6 | **Self-declared "priority days" quota** — N tokens/quarter weight requests 1.5× with optional reason |
| STRETCH | #7 | **Cancellation/release credits** — Release >24h before booking earns small priority credit |

Methodology notes (from the Read Me):

- The whole folder is **synthetic** — user, company, and office names are placeholders,
  verbatims are drawn from a fixed template pool, and emails use the reserved
  `example.invalid` domain.
- The three CSVs (Support Tickets, NPS Responses, Metabase) are **non-overlapping
  populations** — the generator gives each dataset its own users so they read as
  independent evidence streams.

### 3. `Support Tickets.csv` — ~40 synthetic support threads

Each row maps a templated user quote to which of the 8 proposals it supports. The threads
are seeded to illustrate the recurring complaint patterns the proposals address:

- **False-positive no-show suspensions** — auto-suspensions sent in error, clustered so
  that proposal #1's "N offences → forced lowest priority" reads as needing a shadow-mode
  dry-run: the current nudge logic already generates false positives (e.g. department
  cars / overnight stays where gate detection misreads plates on repeated entry/exit).
- **Capacity-transparency defection** — *"I was told there are no available spaces… but
  there are dozens of empty ones… I will just take the first empty space I see."* →
  proposal #4.
- **The "release at 3pm" anti-pattern** — a thread proposing its own deadline-based
  priority drop ("if you don't cancel by 8am then you drop down the priority"), which maps
  to proposals #1 + #7.
- **"Fairness is random"** — a support reply on file states space assignments are
  *"entirely random unless your admin allocates a specific space for you."* → Newton 3 has
  a measurable bar to clear: anything better than random within zones is an improvement.
- **Admin confusion** — an admin warned that manual approvals undermine the "fair
  algorithm." → proposal #3 (priority feed) productises what admins already do by hand.
- **Day-of-week complaints** — Tue/Thu repeatedly rejected — map to proposals #4 + #8: the
  algorithm's day-of-week behaviour is correct but invisible.

### 4. `NPS Responses.csv` — ~320 synthetic NPS verbatims tagged by "Underserved Tier"

Each row carries a templated verbatim, an `Underserved Tier` code, and a `Verbatim
Quality` tag. The tiers are distributed so that **A** (acute) is the largest bucket,
followed by **B** (broad), with **Z**, **M**, **C**, **P**, **X**, and a small
unclassified remainder making up the long tail. Verbatim Quality skews toward
"substantive", then "filler", with a handful of "empty" and "protest" rows.

### 5. `Metabase.csv` — ~1,200 synthetic users with objective metrics

Each row carries the user's measurable history: `approval_rate_pct`,
`rejection_rate_pct`, `used_rate_pct`, `requests_3mo`, `rejected_3mo`,
`unused_bookings_3mo`, `nudge_offences_3mo`, plus group/individual priority,
`has_assigned_space`, `guaranteed_team`. The "Underserved Tier" column is the
classification — see [Underserved Tier Legend](#underserved-tier-legend) below for what
each letter means and the inferred rule that produces it.

The **most important insight**: tier M (the multi-misser bucket, ~6 no-shows / 3 mo) is
exactly who proposal #1 ("N offences → forced lowest priority") targets, while the
false-positive support evidence shows the current no-show detection itself is unreliable.
So #1's bar is: get the detector right *before* enforcing the penalty harder.

---

## Underserved Tier Legend

The four CSVs share the same `Underserved Tier` classification (codes `A`, `B`, `C`, `M`,
`P`, `X`, `Z`, plus blank). The generator assigns each synthetic user a tier from a
per-tier profile; the rules below are **inferred from that per-tier quantile profile in
`Metabase.csv`** and reproduce the partitioning with very few outliers. Treat them as the
working legend for the dataset.

| Code | Mnemonic | One-line definition | Distinguishing rule (inferred) |
|---|---|---|---|
| **A** | **A**cute | Heavy-demand users with the worst approval rates — the **core underserved population** and the largest bucket. | `requests_3mo ≥ ~30` AND `nudge_offences_3mo < 1` AND `unused_bookings_3mo` low; lowest mean approval rate (~5%). |
| **B** | **B**road | Moderate-volume users with below-median approval — the second-largest bucket. | `requests_3mo ~20–45` AND `nudge_offences_3mo < 1`; mean approval ~10%. |
| **C** | **C**asual | Light users (~5–20 req/quarter) who still get more rejection than they expect. | `requests_3mo ~5–20` AND `nudge_offences_3mo == 0`. |
| **M** | **M**ulti-misser | Users with repeated **no-shows** but no formal nudge offences yet — Newton 3's no-show-detection target. | `unused_bookings_3mo ≥ ~3` AND `nudge_offences_3mo < 2`; high p95 unused-booking count. |
| **P** | **P**rivileged | Users holding **guaranteed-team** or **assigned-space** status who still complain — counter-intuitive class that shows the algorithm isn't visible even to its winners. | `guaranteed_team=TRUE` OR `has_assigned_space=TRUE`; lowest rejection rate (~10%), only tier with positive mean `used_rate_pct`. |
| **X** | e**X**cess nudges | Users with **formal nudge offences** (1+ in last 3mo) — proposal #1's target *and* its risk population (the false-positive evidence sits here). | `nudge_offences_3mo ≥ 1`; only tier where the median nudge-offence count is non-zero. |
| **Z** | **Z**ero engagement | Users who barely request parking at all yet complain about the algorithm — likely indicates UX confusion or off-spec use cases. | `requests_3mo ≤ ~2`. |
| *(blank)* | Unclassified | Insufficient signal to categorize — mostly users with zero activity in the observation window. | `bookings_3mo == 0` AND no other distinguishing markers. |

**How to read this:**

- Use **A, B, C** as a **severity ladder** of the core underserved population (high → low
  volume), all with depressed approval rates. A fix that improves outcomes for A first
  should ripple into B and C.
- Tier **M** vs **X** is the most important architectural distinction for proposal #1:
  **M** is users the system *should* start penalising (genuine no-shows), **X** is users
  the system *already is* penalising (nudge offences, including known false positives). A
  scoring model that conflates them inherits the false-positive defect.
- Tier **P** is the canary class: even users with guaranteed seats are voicing pain,
  which means the explainability gap (proposal #8) is global, not just an outcome of
  being rejected.
- Tier **Z** is the **trojan-horse class** for any ML model: training labels that include
  Z users will encode "complains-without-using" as a target signal, which is rarely what
  you want. Filter or down-weight Z in any supervised setup.

---

## Design decisions & critique

Review of the design as specified in [`artifacts/SPEC.md`](artifacts/SPEC.md) and the
[brief](artifacts/CLAUDE.md). The concept, migration strategy, and architecture are
sound; the work concentrates in four areas — the scoring model, the data model, an
explainability/GDPR layer, and tenant configurability — plus two foundational decisions
(when allocation runs, and whether scores persist).

### Assessment at a glance

| Aspect | Rating | Notes |
|---|---|---|
| **Concept & strategy** | Strong | Proven pattern, well-motivated |
| **Migration approach** | Strong | Shadow mode is best practice |
| **Architecture** | Good | Serverless event-driven is the right fit |
| **Scoring model** | Needs work | Too few signals, asymmetric caps, unclear decay |
| **Data model** | Adequate | DynamoDB schema needs GSI refinement |
| **Transparency / GDPR** | Gap | No explainability layer designed |
| **Configurability** | Gap | Hardcoded weights won't survive first enterprise customer |
| **Internal consistency** | Issue | The spec's technical and scoring sections contradict on score persistence |

### 1. Scoring model

#### 1.1 Too few positive signals

The only way to earn points today is carpool participation (`+5`). **Users without a
carpool option have no path to earn rewards at all** — the model can only penalise them.

**Direction:** Add more positive signals and contextual weighting:

- **Early cancellation** — releasing a booking well before the cycle (already proposed as
  `booking.cancelled → +5 if early` in the brief, currently TBD).
- **Consistent attendance** — a streak of booked-and-used spaces.
- **Releasing unused bookings quickly** — rewards giving capacity back while it's still
  reusable, directly attacking the "release at 3pm" anti-pattern in the support tickets.

#### 1.2 The "free space usage" penalty is confusing

The scoring spec penalises a user `-1` for using a "free / shared space." But
**the user was allocated that space — why penalise them for using what the system gave
them?** As written, this reads as arbitrary and erodes trust. **Direction:** either remove
it, or attach a clear justification (e.g. it nudges users toward paid/assigned inventory
for capacity reasons) and surface that reason in the explainability layer. An unexplained
penalty for sanctioned behaviour is worse than no penalty.

#### 1.3 No contextual weighting — occasional vs habitual

A no-show due to illness is penalised identically to habitual abuse. Industry best
practice (ride-hailing apps, Airbnb) distinguishes **occasional** from **pattern**
behaviour.
**Direction:** use a **frequency-based penalty that escalates** — the first no-show in a
window costs little; repeated no-shows within the window cost progressively more. This
aligns with the data: tier **M** (multi-misser, ~6.3 no-shows / 3 mo) is exactly the
pattern-abuse population to escalate against, while a one-off misser should barely move.

#### 1.4 Decay should be tracked per event, not globally

Today decay recovers the whole deficit on a single global timer
(`weeks_since_last_penalty`). This produces unfair asymmetries:

- A user who receives **two penalties in week 1** then behaves perfectly recovers the
  **entire** deficit off one timer.
- A user who gets **one penalty in week 1 and one in week 3** has their decay timer
  **reset** by the second penalty and recovers *more slowly* — despite the same total
  deduction.

**Direction:** track decay **per event**, not globally. Each penalty fades independently
over its own configured window (the pattern used by eBay and Stack Overflow). This removes
the timer-reset penalty and makes recovery predictable.

#### 1.5 Asymmetric caps

The `+20` rolling-4-week reward cap makes the **Platinum (150+) tier unreachable** from
base 100 under the documented mechanics, while penalties have no symmetric ceiling. This
is either a deliberate aspirational tier or an internal inconsistency between the spec's
scoring and technical sections — to be resolved explicitly (see
[Open questions](#open-questions)).

### 2. Data model

**Concern:** DynamoDB sort keys are **ascending only**, so a numeric score sorts
worst-first with no descending option. Descending order requires a **negated** or
**inverted** score, or a composite key.

**Direction:** use a composite GSI keyed for descending score *within a group* in a single
query:

```
GSI1-PK = GROUP#<id>
GSI1-SK = SCORE#<zero-padded-inverted-score>
```

Zero-padding keeps the lexicographic sort numerically correct; inverting the score (e.g.
`9999 - score`) makes ascending lexical order equal descending score order — so a single
`Query` returns the group ranked best-first, exactly what the Allocation Lambda needs.

### 3. Transparency & explainability (GDPR)

Automated decisions that affect users must be explainable. **GDPR Article 22** (and
credit-scoring regulation) requires this for EU users, and it is standard industry
practice: every **credit bureau** provides a "reasons for score change" breakdown;
**ride-hailing apps** show riders which trips affected their rating; **Airbnb** shows
Superhosts exactly which criteria they met or missed.

The `behavior-events` table already stores every event, so the data exists. Expose a
**"score history" / "recent impacts"** view — *"your score is 96; here are the three
events in the last 4 weeks that moved it, and here's how it will recover."*

**Direction:** treat this as a first-class deliverable, not a nice-to-have. It is likely
**legally required for EU users**, directly answers the #1 complaint theme (*"nobody tells
me why"*), and satisfies proposal **#8** (structured rationale on every rejection).

### 4. Configurability

**Problem:** the scoring weights (`-3`, `-1`, `-5`, `+5`) are hardcoded in the design.
Different tenants will want different policies, and a single enterprise customer can block
adoption by demanding their own values.

**Direction:** make at least the following **tenant-configurable from Phase 1** (the spec
already reserves a `tenant-config` DynamoDB table for exactly this):

- Penalty / reward **point values**
- **Decay rate**
- **Reward cap**
- **Which events are enabled**

Defaults ship with the documented values; tenants override per the `tenant-config` record
the Allocation and Scoring Lambdas already fetch.

### 5. Foundational decisions (resolve before building)

#### 5.1 When and how does Newton actually run?

The specs don't pin this down. Is allocation triggered on a **schedule** (e.g. daily
overnight batch), **on-demand**, or **per-booking**? The legacy side runs daily-ish via
the legacy scheduler; the AWS side has a `weekly_decay` EventBridge schedule. The allocation
cadence must be stated explicitly because it constrains everything downstream (and naïvely
reusing SQS visibility-timeout redelivery would double-fire allocations).

#### 5.2 Are scores persistent or ephemeral?

The scoring spec says scores "reset / rerun after each major allocation cycle."
**If scores reset after each allocation, the decay model, tier assignments, and
user-visible scores become meaningless between allocations** — and it couples the
allocation cycle to the scoring engine, undermining the event-driven design.

**Direction:** make scores **persistent — event-sourced and continuously updated**, not
ephemeral. Persistent scores are more scalable (no full recompute per cycle), more
transparent (users see a stable, always-current score), and real-time queryable (the
`GET /users/{id}/behavior-score` API returns a live value, not a stale snapshot). This is
also the only model under which the explainability layer (§3) and the per-event decay
model (§1.4) are coherent.

---

## Open questions

Things the spec leaves open:

1. **Reward cap vs Platinum tier** — is Platinum (150+) reachable, or deliberately
   aspirational / contingent on something not in the spec? (§1.5)
2. **Score reset semantics** — the spec's scoring section says "score resets/reruns after
   each major allocation cycle"; the CLAUDE.md and technical section don't restate it.
   Reset to 100, or reset *within a cycle's scoring window only*? (§5.2)
3. **Score scope** — is `behavior_score` per-user or per-(user, group)? The DynamoDB key
   `USER#id / GROUP#id` suggests scoped, but the spec's examples ("User: John score=104")
   read as global. Matters for users in multiple groups across offices.
4. **Free-space penalty justification** — keep with a stated rationale, or drop? (§1.2)
5. **Allocation cycle granularity** — daily, weekly, or per-request? (§5.1)
6. **Proposal #2 (approval-rate parity)** — a fourth scoring input, or a replacement of
   score-based ranking entirely? The two are architecturally different.
7. **Underserved Tier legend confirmation** — the [legend](#underserved-tier-legend) is
   *inferred* from the per-tier quantile profile; confirming it against the generator's
   tier definitions makes the codes authoritative for supervised learning.

---

## Deliverables

A complete submission provides:

- **Demo** — a runnable CLI / API or a short walkthrough
- **Documentation** — this spec and the design notes above
- **Architecture / technical overview** — the AWS topology and module layout
