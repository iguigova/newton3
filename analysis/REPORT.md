# Data audit — behaviour score over the underserved users

Source: `docs/artifacts/…Metabase.csv` (1200 users with a `user_id`). Reference date 2026-06-01. Method + caveat: see the module docstring in `analysis/impact.py`. Reproduce with `python -m analysis.impact`.

## 1. Behaviour score by analyst Underserved Tier

Mean score under the documented defaults vs a long-memory tenant profile (90-day windows). Lower is worse.

| Tier | n | mean (defaults) | mean (long-memory) | min | % Bronze-or-below |
|---|---|---|---|---|---|
| A | 468 | 100.0 | 96.7 | 86 | 0% |
| B | 216 | 99.9 | 94.2 | 83 | 0% |
| C | 108 | 100.0 | 97.9 | 91 | 0% |
| M | 96 | 99.5 | 88.8 | 77 | 5% |
| P | 36 | 99.9 | 93.8 | 87 | 0% |
| X | 36 | 98.9 | 90.9 | 59 | 11% |
| Z | 240 | 100.0 | 99.2 | 93 | 0% |

## 2. Behaviour-tier distribution (long-memory profile)

| Tier | n | % |
|---|---|---|
| Platinum | 0 | 0% |
| Gold | 0 | 0% |
| Silver | 1191 | 99% |
| Bronze | 9 | 1% |
| Restricted | 0 | 0% |

Score percentiles: p10 **91**, median **97**, min **59**. Most users sit at or near base; the tail is where the behaviour layer does its work.

## 3. Where the behaviour layer acts (shadow view)

Behaviour is layer 3 — it only changes order *within* an admin-priority bracket, where the legacy system fell back to a **random** tie-break. So the honest question is not 'how many move' (random has no fixed order) but 'where does behaviour have signal to act'.

- **1200 / 1200** users share a bracket with at least one other user (7 multi-user brackets) — there the random tie-break is replaced by a deterministic, explainable order.
- The largest bracket holds **1039** users with scores spanning **59–100** — ample signal to order them fairly instead of by chance.

## 4. Offence override (#1) — illustrative threshold 2 / 30 days

**4 / 1200** users trip the override and are force-ranked last — the repeat-offence population proposal #1 targets. Threshold and window are tenant-configurable.

## Reading

- **Defaults barely move the score** — the short no-show window (7 days) hides a 3-month history. A real finding, and the argument for tenant-configurable windows.
- **Long-memory separates cleanly:** tiers **M** (multi-misser) and **X** (excess nudges) sink; the high-demand underserved **A, B, C** keep near-base scores.
- So the behaviour layer **separates the core underserved from genuine abusers** — it pushes abuse *down* while leaving A/B/C near base (it does not lift them *up*: carpool is the only default reward). The same engine does both, by config.
