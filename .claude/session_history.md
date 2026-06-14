# Session History

## 2026-06-13 — Design re-evaluation

Re-read the Newton 3 design/spec against the goal it serves, after the prototype surfaced
that the documented defaults barely move scores and the behaviour layer helps no one up.

**Finding:** the spec optimised a mechanism (per-user behaviour score) that addresses none
of the three driving complaints well and worsens the false-penalty one. Goal restated as:
make the rationing of a scarce work necessity feel fair, legible, and correct to the people
who lose the lottery.

**Changes (docs only, no code):**
- Added `docs/REEVALUATION.md` — critique + decisions on all eleven open questions.
- Added `docs/SPEC.v2.md` — redesigned spec organised around objective + metrics; behaviour
  score demoted to an optional off-by-default layer; approval-rate parity promoted to the
  primary fairness layer; explainability/capacity/waitlist/overbooking made core; tier
  ladder and free-space penalty removed; architecture right-sized; supersedes
  `docs/artifacts/SPEC.md`.
- Linked both from `docs/README.md` and top-level `README.md`.

Suggested commit message:
`docs: re-evaluate design — demote behaviour score, lead with objective + metrics (SPEC.v2)`
