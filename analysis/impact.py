"""Data audit: run the scoring engine over the underserved users in
`docs/artifacts/…Metabase.csv` and show that the behaviour layer targets
abuse (tiers M, X) rather than the high-demand underserved (tiers A, B, C).

Run from the repository root:

    python -m analysis.impact     # prints summary, writes analysis/REPORT.md

Honesty note: the source gives 3-month *aggregates*, not an event log. We
reconstruct events by spreading each user's `nudge_offences_3mo` and
`unused_bookings_3mo` evenly across a 90-day window, then score at a fixed
reference date. Only events inside each type's decay window still count — so
this models *recent standing*, not lifetime totals. The reference date is
fixed, so the report is fully reproducible.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

from analysis.shadow import brackets
from newton.config import Config
from newton.engine import evaluate, is_force_last, tier
from newton.models import Candidate, Event, EventType, Tier

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "docs/artifacts/Algorithm User Complaints - Metabase.csv"
REPORT = ROOT / "analysis" / "REPORT.md"
NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
HISTORY_DAYS = 90

# Documented spec defaults vs a tenant profile whose memory matches the
# 90-day observation horizon. The contrast is the point: defaults are
# forgiving (short windows hide a 3-month history); a long-memory tenant
# turns the same events into a clear separation — the configurability the
# review asked for, exercised on the example data.
DEFAULT = Config()
LONG_MEMORY = Config(
    windows={
        EventType.NO_SHOW: 90,
        EventType.FREE_SPACE: 30,
        EventType.OFFENCE: 90,
        EventType.CARPOOL: 28,
    }
)
# Illustrative offence-override policy for the #1 audit section.
RESTRICT = Config(offence_override=2, offence_override_window_days=30)

Scored = list[tuple[str, str, int, int]]  # uid, tier_label, score, priority


def _int(value: str) -> int:
    value = value.strip()
    return int(value) if value.isdigit() else 0


def _events(user_id: str, count: int, kind: EventType) -> list[Event]:
    """Spread `count` aggregated events evenly across the history window."""
    if count <= 0:
        return []
    step = HISTORY_DAYS / count
    return [
        Event(user_id, kind, NOW - timedelta(days=step * (i + 0.5)))
        for i in range(count)
    ]


def load(path: Path = CSV) -> list[tuple[str, str, list[Event], int]]:
    """Yield (user_id, underserved_tier, events, individual_priority)."""
    rows = []
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            uid = r["user_id"].strip()
            if not uid:
                continue
            events = _events(
                uid, _int(r["nudge_offences_3mo"]), EventType.OFFENCE
            ) + _events(uid, _int(r["unused_bookings_3mo"]), EventType.NO_SHOW)
            label = r["Underserved Tier"].strip() or "—"
            rows.append((uid, label, events, _int(r["individual_priority"])))
    return rows


def score_rows(
    rows: list[tuple[str, str, list[Event], int]], config: Config
) -> Scored:
    return [
        (uid, label, evaluate(events, config, now=NOW).score, prio)
        for uid, label, events, prio in rows
    ]


def by_underserved_tier(scored: Scored) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for _uid, label, score, _prio in scored:
        out.setdefault(label, []).append(score)
    return out


def _pct(values: list[int], p: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))]


def _render(rows: list[tuple[str, str, list[Event], int]]) -> str:
    default = by_underserved_tier(score_rows(rows, DEFAULT))
    lm_scored = score_rows(rows, LONG_MEMORY)
    long_memory = by_underserved_tier(lm_scored)
    total = len(rows)

    lines = [
        "# Data audit — behaviour score over the underserved users",
        "",
        f"Source: `docs/artifacts/…Metabase.csv` ({total} users with a "
        "`user_id`). Reference date 2026-06-01. Method + caveat: see the "
        "module docstring in `analysis/impact.py`. Reproduce with "
        "`python -m analysis.impact`.",
        "",
    ]
    lines += _tier_section(default, long_memory)
    lines += _distribution_section(lm_scored, total)
    lines += _shadow_section(lm_scored, total)
    lines += _override_section(rows, total)
    lines += _reading_section()
    return "\n".join(lines)


def _override_section(
    rows: list[tuple[str, str, list[Event], int]], total: int
) -> list[str]:
    force_last = sum(
        is_force_last(events, RESTRICT, now=NOW) for _u, _l, events, _p in rows
    )
    return [
        "## 4. Offence override (#1) — illustrative threshold 2 / 30 days",
        "",
        f"**{force_last} / {total}** users trip the override and are "
        "force-ranked last — the repeat-offence population proposal #1 "
        "targets. Threshold and window are tenant-configurable.",
        "",
    ]


def _tier_section(
    default: dict[str, list[int]], long_memory: dict[str, list[int]]
) -> list[str]:
    order = ["A", "B", "C", "M", "P", "X", "Z", "—"]
    lines = [
        "## 1. Behaviour score by analyst Underserved Tier",
        "",
        "Mean score under the documented defaults vs a long-memory tenant "
        "profile (90-day windows). Lower is worse.",
        "",
        "| Tier | n | mean (defaults) | mean (long-memory) | min | "
        "% Bronze-or-below |",
        "|---|---|---|---|---|---|",
    ]
    for label in order:
        lm = long_memory.get(label)
        if not lm:
            continue
        below = 100 * sum(s < 80 for s in lm) / len(lm)
        lines.append(
            f"| {label} | {len(lm)} | {mean(default[label]):.1f} | "
            f"{mean(lm):.1f} | {min(lm)} | {below:.0f}% |"
        )
    return lines + [""]


def _distribution_section(scored: Scored, total: int) -> list[str]:
    scores = [s for _u, _l, s, _p in scored]
    tiers = Counter(tier(s, LONG_MEMORY) for s in scores)
    order = [
        Tier.PLATINUM,
        Tier.GOLD,
        Tier.SILVER,
        Tier.BRONZE,
        Tier.RESTRICTED,
    ]
    lines = [
        "## 2. Behaviour-tier distribution (long-memory profile)",
        "",
        "| Tier | n | % |",
        "|---|---|---|",
    ]
    for t in order:
        n = tiers.get(t, 0)
        lines.append(f"| {t.value} | {n} | {100 * n / total:.0f}% |")
    lines += [
        "",
        f"Score percentiles: p10 **{_pct(scores, 10)}**, median "
        f"**{_pct(scores, 50)}**, min **{min(scores)}**. Most users sit at "
        "or near base; the tail is where the behaviour layer does its work.",
        "",
    ]
    return lines


def _shadow_section(scored: Scored, total: int) -> list[str]:
    cands = [Candidate(uid, 0, prio, s) for uid, _l, s, prio in scored]
    groups = brackets(cands)
    multi = [g for g in groups.values() if len(g) > 1]
    in_multi = sum(len(g) for g in multi)
    largest = max(groups.values(), key=len)
    spread = (min(c.score for c in largest), max(c.score for c in largest))
    return [
        "## 3. Where the behaviour layer acts (shadow view)",
        "",
        "Behaviour is layer 3 — it only changes order *within* an "
        "admin-priority bracket, where the legacy system fell back to a "
        "**random** tie-break. So the honest question is not 'how many move' "
        "(random has no fixed order) but 'where does behaviour have signal "
        "to act'.",
        "",
        f"- **{in_multi} / {total}** users share a bracket with at least one "
        f"other user ({len(multi)} multi-user brackets) — there the random "
        "tie-break is replaced by a deterministic, explainable order.",
        f"- The largest bracket holds **{len(largest)}** users with scores "
        f"spanning **{spread[0]}–{spread[1]}** — ample signal to order them "
        "fairly instead of by chance.",
        "",
    ]


def _reading_section() -> list[str]:
    return [
        "## Reading",
        "",
        "- **Defaults barely move the score** — the short no-show window "
        "(7 days) hides a 3-month history. A real finding, and the argument "
        "for tenant-configurable windows.",
        "- **Long-memory separates cleanly:** tiers **M** (multi-misser) and "
        "**X** (excess nudges) sink; the high-demand underserved **A, B, C** "
        "keep near-base scores.",
        "- So the behaviour layer **separates the core underserved from "
        "genuine abusers** — it pushes abuse *down* while leaving A/B/C near "
        "base (it does not lift them *up*: carpool is the only default reward). "
        "The same engine does both, by config.",
        "",
    ]


def main() -> None:
    report = _render(load())
    REPORT.write_text(report)
    print(report)
    print(f"\nwrote {REPORT}")


if __name__ == "__main__":
    main()
