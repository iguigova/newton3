# Share note

A short note for sharing the project. Fill in the demo link before sending.

## Long form

> Newton 3 is a behaviour-driven allocation engine for shared workplace resources —
> parking, desks, EV chargers.
>
> - **Demo (~5 min):** <LINK>
> - **Start here:** `deliverables/README.md` maps every part of the project.
>
> The short version: Newton 3 reframes the behaviour score as a **pure fold over an event
> log** — `score(events, config, now)` — instead of stored state. That one decision makes
> persistence, per-event decay, explainability, and per-tenant configurability **properties
> of the function rather than subsystems to build**, and removes the weekly decay job
> entirely. Every score and every allocation outcome carries its own reconciling reason
> (GDPR Art. 22 — the "nobody tells me why" problem). It ships with a runnable, curl-able
> read API (standard library only, nothing to install) and an ML stretch — a predictive
> no-show model that sizes overbooking while staying **out** of the score, so the ranking
> stays explainable. On the synthetic 1,200-user dataset the documented defaults barely move
> any score — a genuine finding that makes the case for tenant-configurable windows; tuned
> to the data, the same engine separates genuine abuse (tiers M, X) from the high-demand
> underserved (A, B, C), and a shadow comparator shows exactly where it acts before any
> cut-over.
>
> What the project does not claim is in `deliverables/README.md`'s honesty ledger — the
> open design questions are noted there too.

## Short form

> *Newton 3* :rocket:
>
> • Demo (~5 min): <LINK>
> • Start at `deliverables/README.md`
>
> TL;DR — Newton 3 makes the behaviour score a *pure fold over an event log* instead of
> stored state, so persistence, per-event decay, explainability, and per-tenant config are
> properties of one function (and the weekly decay job is gone). Ships a runnable, curl-able
> read API (stdlib only) + an ML stretch — predictive no-show → overbooking — that stays
> *out* of the score so ranking stays explainable. On the synthetic 1,200-user data the default
> windows barely move the score (the case for per-tenant config); tuned, the same engine
> separates genuine abuse from the underserved. Honesty ledger + open questions in this
> repository.
