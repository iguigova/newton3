# Newton 3 — Insights & Future Improvements

What the build and the data audit actually taught us, and where this goes next.
Evidence lives in [`analysis/REPORT.md`](../analysis/REPORT.md) and
[`analysis/scenarios.py`](../analysis/scenarios.py); open design questions the author
must settle are in [`docs/README.md`](../docs/README.md#open-questions).

## Insights

1. **The score is one pure fold — most "subsystems" were illusions.** Persistence,
   per-event decay, explainability, and configurability are *properties* of
   `score(events, config, now)`, not components to build. The weekly decay Lambda
   disappears entirely (decay is computed at read time). Less code, fewer moving parts,
   nothing to keep in sync.

2. **The documented defaults are too forgiving for historical behaviour.** With a 7-day
   no-show window, a 3-month history is nearly invisible — on the example data, mean scores
   barely leave 100 under defaults (`REPORT.md §1`). This is a genuine finding, not a
   bug: the windows are a *policy*, and the right ones are tenant-specific. It is the
   strongest argument for making windows configurable from day one.

3. **With memory matched to the data, the layer does its job — downward.** Under a
   long-memory profile the multi-misser tier **M** drops to a mean of ~90 (16%
   Bronze-or-below, min 38) and excess-nudge tier **X** to ~93, while the high-demand
   underserved **A, B, C** stay near base. The behaviour layer **penalises genuine abuse
   and spares the people who were actually underserved** — the *same engine* does both,
   by config alone. Note the asymmetry, by design: with carpool the only default reward,
   it pushes abusers *down* but cannot lift good users *up*. That one-sidedness is a
   policy gap, not a structural one — see [future improvements](#future-improvements).

4. **Behaviour matters where admin priority doesn't — for the users who have a history.**
   It is layer 3, so it only reorders users inside an equal-priority bracket, and in the
   data **1,030 of 1,200** users sit in the largest such bracket (`REPORT.md §3`). But it only
   *separates* users whose events actually moved their score; the bulk of the population
   sits at or near base 100 (median 98), still tied and still needing a tie-break. Where
   there *is* signal, Newton 3 replaces the legacy *random* tie-break with a
   deterministic, explainable order — a real but **partial** answer to *"allocation feels
   random,"* not a blanket one. Broadening the signal (insight 3) is what widens it.

5. **A known tension remains by design.** The +20 rolling reward cap makes the Platinum
   tier (150+) unreachable from base 100. Either Platinum is aspirational or the cap and
   tiers disagree — flagged, not hidden (`docs/README.md` open question 1).

## Proposals from the complaint analysis

- **#8 explainability — delivered.** `decide()` attaches a rationale to every allocation
  outcome (your rank, the bracket above you, the behaviour cutoff); `behavior_score`
  returns the score's own trace.
- **#1 offence override — delivered.** `Config.offence_override` force-ranks repeat
  offenders last; threshold and window are tenant-configurable. Enforce only behind a
  proven offence detector (the false-positive offence-detection risk).
- **#3 customer priority feed — next.** Accept a weekly tenant priority list as layer-1
  input.
- **#2 approval-rate parity — open.** Decide whether it is a fourth scoring input or a
  different ranking basis; the specs disagree.

## Future improvements

**Scoring model**
- More positive signals so users without a carpool option can earn standing — the fix
  for the one-sidedness in insight 3. `EARLY_RELEASE` (the brief's TBD "early cancel +5")
  now ships as a first-class event, **disabled by default**; a tenant turns it on with a
  weight + window (`test_engine.py::test_tenant_can_enable_early_release_to_earn_standing`).
  Consistent-attendance *streaks* need state the per-event fold doesn't model — a
  deliberate next step, not a config flag.
- Decide the free-space `-1` penalty: justify it (and surface the reason) or drop it.
- Escalation is implemented but off by default; tune per tenant once policy is set.

**Productionisation**
- Swap `InMemoryStore` for `DynamoEventStore(EventStore)` — no change above the store.
- Replace the mock `legacy_rank` with a diff against *real* legacy output for true shadow
  mode; gate cut-over on the divergence review.
- For scale, materialise the ranked GSI as a score snapshot plus a `next-change-at`
  timestamp and refresh lazily (the read-time fold stays the source of truth).

**AI / stretch (the stretch tier)**
- **Predictive no-show → overbooking — shipped.** `analysis/predict.py` trains a
  pure-Python logistic-regression model on the Metabase features (64% lower error than a
  predict-the-mean baseline, calibrated to the real ~8% no-show rate) and turns predicted
  attendance into an overbooking factor. It is **composed, not coupled**: it feeds
  *capacity*, not *ranking*, so the behaviour score stays a pure, explainable fold and no
  black box ever decides who gets a space.
- LLM-generated natural-language explanation built *from* the impact trace (grounded, not
  hallucinated) — next.
- Anomaly detection over event streams to flag detector errors (e.g. ANPR misreads)
  before they become penalties — next.
