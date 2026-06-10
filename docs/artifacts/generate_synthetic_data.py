"""Generate the synthetic example dataset under ``docs/artifacts/``.

Everything in this folder is **fully synthetic** — no real users, companies, or
support text. This script is the single source of that data: it emits the four
CSVs the docs and analysis read, with a fixed seed so the output is
reproducible bit-for-bit.

The data is shaped to exercise the scoring engine realistically:

- Users are split into *underserved tiers* (A/B/C high-demand underserved,
  M multi-misser, X excess-offence, P/Z/— low-signal). The abuse tiers (M, X)
  carry more unused bookings and offences, so the behaviour layer separates
  them from the high-demand underserved — the property the audit reports.
- ``unused_bookings`` is generated as a noisy function of demand and offence
  count, so the no-show predictor in ``analysis/predict.py`` finds real signal
  rather than just the mean.
- Most users share a blank individual priority, forming one large allocation
  bracket where the behaviour score is the sole tie-break — the shadow view.

Regenerate with::

    python docs/artifacts/generate_synthetic_data.py
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20260601
N_USERS = 1200

# (tier, share, requests_mean, unused_rate, nudge_rate, approval, rejection, used)
# unused_rate / nudge_rate are per-user expected counts over the 3-month window.
# Abuse tiers M, X sit high on unused / nudge; A/B/C stay low.
TIERS = [
    ("A", 0.39, 48, 2.1, 0.10, 5, 20, 2.5),
    ("B", 0.18, 33, 3.7, 0.13, 10, 18, 1.8),
    ("C", 0.09, 17, 1.7, 0.01, 6, 19, 0.1),
    ("M", 0.08, 41, 6.3, 0.33, 17, 14, 1.1),
    ("P", 0.03, 49, 4.1, 0.12, 14, 10, 3.2),
    ("X", 0.03, 43, 2.8, 1.15, 6, 14, 1.7),
    ("Z", 0.14, 3, 0.8, 0.05, 6, 6, 0.0),
    ("", 0.06, 2, 0.05, 0.04, 0, 3, 0.0),
]

IMPROVEMENT_AREAS = [
    "Booking policy & algorithm",
    "Access control",
    "Using the booking app",
    "App experience",
    "Pricing & credits",
    "Notifications",
]
COMPLAINTS = [
    "Allocation feels random — I never get the days I ask for and no reason is given.",
    "I keep losing Tuesdays to the same people and there's no visibility into why.",
    "Was marked as a no-show for a booking I released the night before.",
    "No way to see my position when a request is rejected.",
    "Carpooling never seems to help my chances even though I do it weekly.",
    "Would love to see how full a day is before I request it.",
    "The priority rules are opaque; I can't explain them to my team.",
    "A waitlist with a visible position would be far better than a flat rejection.",
]
PROPOSALS = ["#1", "#2", "#3", "#4", "#5", "#6", "#7", "#8"]
ROLES = ["User", "User", "User", "Admin"]


def _pois(rng: random.Random, mean: float) -> int:
    """Small-count Poisson draw (Knuth), fine for the means used here."""
    import math

    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _assign_tiers(rng: random.Random) -> list[str]:
    labels: list[str] = []
    for tier, share, *_ in TIERS:
        labels += [tier] * round(share * N_USERS)
    while len(labels) < N_USERS:
        labels.append("A")
    rng.shuffle(labels)
    return labels[:N_USERS]


def _metabase_row(rng: random.Random, i: int, tier: str) -> dict:
    spec = next(t for t in TIERS if t[0] == tier)
    _, _, req_mean, unused_rate, nudge_rate, appr, rej, used = spec
    requests = _pois(rng, req_mean)
    nudge = _pois(rng, nudge_rate)
    # A small repeat-offender tail in the excess-offence tier — enough users
    # to make the #1 offence-override demo (>=2 offences / 30 days) non-empty.
    if tier == "X" and rng.random() < 0.12:
        nudge += rng.randint(4, 8)
    # unused depends on demand AND offences — the signal the predictor learns.
    lam = unused_rate * (1 + 0.15 * nudge) * (requests / max(req_mean, 1))
    unused = min(requests, _pois(rng, max(0.0, lam)))
    bookings = max(0, requests - rng.randint(0, max(0, requests - unused)))
    rejected = max(0, requests - bookings)
    # Most users share a blank priority -> one large bracket; a few differ.
    priority = "" if rng.random() < 0.86 else str(rng.randint(1, 6))
    daily = '["", "", "", "", "", "", ""]'
    if priority:
        p = priority
        daily = f'["", "{p}", "{p}", "{p}", "{p}", "{p}", ""]'
    cid = f"{rng.randint(1, 180):04d}"
    return {
        "user_id": f"user-{i:05d}",
        "user_name": f"User {i:05d}",
        "company_name": f"Company {int(cid):03d}",
        "office_name": f"Office {rng.randint(1, 120):03d}",
        "group_name": f"Group {rng.randint(1, 90):03d}",
        "guaranteed_team": rng.choice(["FALSE"] * 9 + ["TRUE"]),
        "team_daily_priority": daily,
        "individual_priority": priority,
        "has_assigned_space": "Yes" if rng.random() < 0.02 else "No",
        "requests_3mo": requests,
        "bookings_3mo": bookings,
        "rejected_3mo": rejected,
        "unused_bookings_3mo": unused,
        "nudge_offences_3mo": nudge,
        "approval_rate_pct": max(0, round(rng.gauss(appr, 5))),
        "rejection_rate_pct": max(0, round(rng.gauss(rej, 5))),
        "used_rate_pct": max(0, round(rng.gauss(used, 2))),
        "company_id": "",
        "office_id": cid,
        "Underserved Tier": tier or "Z",
    }


def write_metabase(rng: random.Random, tiers: list[str]) -> list[dict]:
    rows = [_metabase_row(rng, i + 1, tiers[i]) for i in range(N_USERS)]
    path = HERE / "Algorithm User Complaints - Metabase.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


def write_nps(rng: random.Random, rows: list[dict]) -> None:
    fields = [
        "Response Date", "Company", "Office", "User ID", "Name", "Email",
        "Role", "Score", "Improvement Area", "Verbatim", "Survey Language",
        "Underserved Tier", "Verbatim Quality",
    ]
    sample = rng.sample(rows, 320)
    path = HERE / "Algorithm User Complaints - NPS Responses.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sample:
            n = int(r["user_id"].split("-")[1])
            areas = ", ".join(rng.sample(IMPROVEMENT_AREAS, rng.randint(1, 3)))
            w.writerow({
                "Response Date": f"{rng.randint(1, 28):02d}/0{rng.randint(1, 6)}/2026",
                "Company": r["company_name"],
                "Office": r["office_name"],
                "User ID": r["user_id"],
                "Name": r["user_name"],
                "Email": f"user{n:05d}@example.invalid",
                "Role": rng.choice(ROLES),
                "Score": rng.choice(["", "0", "2", "4", "6", "8", "10"]),
                "Improvement Area": areas,
                "Verbatim": rng.choice(COMPLAINTS),
                "Survey Language": "en",
                "Underserved Tier": r["Underserved Tier"],
                "Verbatim Quality": rng.choice(["filler", "substantive"]),
            })


def write_support(rng: random.Random, rows: list[dict]) -> None:
    fields = [
        "Date", "Company", "Office", "User ID", "Name", "Email", "Role",
        "Verbatim", "Proposals", "Notes",
    ]
    sample = rng.sample(rows, 40)
    path = HERE / "Algorithm User Complaints - Support Tickets.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sample:
            n = int(r["user_id"].split("-")[1])
            props = ", ".join(rng.sample(PROPOSALS, rng.randint(1, 2)))
            w.writerow({
                "Date": f"2026-0{rng.randint(1, 6)}-{rng.randint(1, 28):02d}",
                "Company": r["company_name"],
                "Office": r["office_name"],
                "User ID": r["user_id"],
                "Name": r["user_name"],
                "Email": f"user{n:05d}@example.invalid",
                "Role": rng.choice(ROLES),
                "Verbatim": rng.choice(COMPLAINTS),
                "Proposals": props,
                "Notes": "synthetic sample",
            })


def write_readme() -> None:
    path = HERE / "Algorithm User Complaints - Read Me.csv"
    lines = [
        ["NEWTON 3 — SYNTHETIC EXAMPLE DATASET", "", "", ""],
        ["", "", "", ""],
        ["All rows in this folder are generated, not real. See "
         "generate_synthetic_data.py.", "", "", ""],
        ["", "", "", ""],
        ["PROPOSAL LEGEND (referenced as #1-#8 in the Proposals column)",
         "", "", ""],
        ["Tier", "#", "Proposal", "Mechanism (one-line)"],
        ["MANDATORY", "#1", "Threshold-based offence override",
         "N offences in 30 days -> forced lowest priority"],
        ["MANDATORY", "#3", "Customer priority feed API",
         "Accepts a weekly JSON priority list owned by the customer"],
        ["MANDATORY", "#8", "Native explainability surface",
         "Every rejection includes a structured rationale"],
        ["HIGH-VALUE", "#2", "Approval-rate parity",
         "30-day approval rate vs office median -> priority bump/dip"],
        ["HIGH-VALUE", "#4", "Real-time capacity transparency",
         "Show estimated chance at request time; suggest alternates"],
        ["HIGH-VALUE", "#5", "Explicit waitlist mechanism",
         "Rejected -> ranked waitlist with visible position"],
        ["STRETCH", "#6", "Self-declared priority days",
         "N tokens per quarter weight a request more heavily"],
        ["STRETCH", "#7", "Cancellation/release credits",
         "Releasing early earns a small priority credit"],
        ["", "", "", ""],
        ["METHODOLOGY", "", "", ""],
        ["Synthetic. User, company, and office names are placeholders; "
         "verbatims are drawn from a fixed template pool; emails use the "
         "reserved example.invalid domain.", "", "", ""],
    ]
    with path.open("w", newline="") as f:
        csv.writer(f).writerows(lines)


def main() -> None:
    rng = random.Random(SEED)
    tiers = _assign_tiers(rng)
    rows = write_metabase(rng, tiers)
    write_nps(rng, rows)
    write_support(rng, rows)
    write_readme()
    print(f"wrote {N_USERS} users + NPS + support + read-me to {HERE}")


if __name__ == "__main__":
    main()
