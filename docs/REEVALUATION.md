# Newton 3 — Re-evaluation

A critical re-read of the design after building the prototype. It states the goal the
project actually serves, names where the spec optimised the wrong thing, and records the
decision taken on every open question. The forward design that follows from it is
[`SPEC.v2.md`](./SPEC.v2.md); the original brief is preserved in
[`artifacts/SPEC.md`](./artifacts/SPEC.md).

---

## The goal, plainly

Newton 3 rations a scarce work necessity — parking, desks, EV chargers — when demand
exceeds supply. It exists to fix three complaints about the legacy allocator:

1. *"Allocation feels random."* → the order must be **predictable and fair**.
2. *"I never get Tuesdays and nobody tells me why."* → the system must be **transparent**,
   and give people a real shot at the days they need.
3. *"I was penalised for a no-show I didn't commit."* → penalties must be **accurate and
   contestable**.

The goal is therefore: **make the rationing of a scarce work necessity feel fair, legible,
and correct to the people who lose the lottery.** "Behaviour-driven scoring," "AWS-native,"
and "AI-ready" are mechanisms that were chosen — they are not the goal, and the original
spec substitutes one for the other.

## The core finding

The flagship mechanism — a per-user behaviour score — addresses none of the three
complaints well, and worsens one of them. The prototype's own audit establishes this:

- Under the documented defaults, **mean scores barely leave 100**
  ([`analysis/REPORT.md` §1](../analysis/REPORT.md)) — the mechanism does almost nothing.
- Making it act at all required a "long-memory profile" the spec never defined — the
  published point values are arbitrary because no objective pins them down.
- It only **pushes abusers down, never lifts good users up** (carpool is the sole default
  reward), so the underserved high-demand tiers **A, B, C** — the population the project is
  named for — keep near-base scores. The headline mechanism does nothing for the people it
  is meant to help ([`deliverables/INSIGHTS.md` §3](../deliverables/INSIGHTS.md)).
- It only de-randomises **within an equal-priority bracket, and only for users whose
  events moved their score.** The median user sits at 98, still tied, still random — a
  partial answer to *"allocation feels random,"* for a minority.

## Where the design went wrong

1. **Mechanism mistaken for goal.** The score was decided first; the spec then tuned
   `-3 / -1 / -5 / +5`, caps, decay, and tiers. There is **no objective function and no
   success metric** anywhere. That absence is why the spec contradicts itself (Platinum
   unreachable, reset-vs-persistent, per-event-vs-global decay, score scope, free-space
   penalty): the numbers were set before "good" was defined.

2. **The score is regressive and orthogonal to fairness.** It has a floor (0), an
   unreachable ceiling (Platinum 150+), and one way up. It is a punishment engine with a
   loyalty-tier veneer. The mechanism that would actually equalise fairness —
   **approval-rate parity (#2)**, bumping users whose approval sits below the office median
   — is filed as a "high-value open question."

3. **It amplifies complaint #3.** The no-show detector is known to be unreliable (ANPR
   misreads, department cars, overnight stays). Baking that noisy signal into a persistent,
   person-attached score productises the defect instead of fixing it.

4. **The real problem is scarcity, and the score does not touch it.** Reordering who is
   first in a bracket rejects the same number of people. The levers that change outcomes
   are supply-side — overbooking from no-show prediction (already shipped, 64% better than
   baseline), fast release of unused bookings, waitlist auto-promotion. These were demoted;
   the score that changes nobody's odds was given top billing.

5. **The architecture is premature.** Multi-region DynamoDB Global Tables, an EventBridge
   bus, and a Lambda fleet describe infrastructure that a pure fold over an event log, run
   as an office-sized batch, does not need. The prototype already collapsed most of it:
   "most subsystems were illusions," the decay Lambda "disappears entirely."

6. **The polish hides all of this.** The docs are cross-linked and self-critical, which
   manufactures confidence. The existing critique treats each flaw as a detail to fix
   *inside* the chosen frame, never as evidence the frame is wrong.

## Open questions → decisions

The original spec and synthesis leave eleven questions open. An unmade decision in a v3
spec is a defect, not a feature. Each is now resolved; the forward design implements these.

| # | Open question | Decision | Rationale |
|---|---|---|---|
| 1 | Reward cap vs Platinum tier | **Remove the tier ladder.** | Gamifying access to a work necessity is an equity and HR-liability risk that buys no measured outcome; the cap-vs-Platinum contradiction disappears with the tiers. |
| 2 | Free-space `-1` penalty | **Drop it.** | Penalising a user for using the space the system gave them is indefensible and erodes the trust the project exists to build. |
| 3 | Allocation cadence | **Scheduled per-cycle batch**, at the organisation's existing cadence. | The score is computed at read time, so cadence never couples to scoring; per-request allocation is out of scope. |
| 4 | Score scope (per-user vs per-group) | **Per-(user, tenant), evaluated in group context.** | Brackets are group-scoped, but the score is a minor tie-breaker, so a single per-user value carried into each bracket is sufficient and simpler. |
| 5 | Approval-rate parity (#2) | **Promote to the primary within-bracket fairness basis**, not a fourth score input. | This is the only mechanism that helps the named underserved population A/B/C; the score cannot. |
| 6 | Score reset semantics | **Persistent and event-sourced; never reset.** | The pure read-time fold already implies this; resetting would void decay, history, and the API. |
| 7 | Behaviour score role | **Demote to an optional, off-by-default tie-breaker.** | It de-randomises for a minority and helps no one up; it is a nudge, not the product. |
| 8 | No-show detector → penalty | **A noisy detector may inform capacity (soft), never a persistent person-penalty (hard), until its accuracy is proven; penalties are decaying and contestable.** | Directly answers complaint #3 instead of productising the defect. |
| 9 | Architecture scale | **Right-size to the real load**: pure fold + one store + read API; defer the bus, Lambda fleet, and Global Tables until a real load justifies them. | The computation does not need the infrastructure the spec describes. |
| 10 | Underserved Tier legend | **Analysis scaffolding only**; nothing in the product depends on it. | The legend is inferred; confirm it against the generator before any supervised use, but keep it out of the allocation path. |
| 11 | Success definition | **Define an objective and metrics first** (see [`SPEC.v2.md` §1](./SPEC.v2.md)). | Every feature is justified against a metric, or it is cut. |

## The pivot, in one line

Newton 3 was built as a behaviour-scoring engine for a problem that is really about
transparency and scarcity. Keep the engine as a small optional nudge; make explainability,
capacity transparency, waitlists, overbooking, and approval-rate parity the product — and
stop letting an unreliable no-show detector punish people.
