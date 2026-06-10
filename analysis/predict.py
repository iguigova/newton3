"""Predictive no-show → overbooking: the ML stretch, composed so it never
touches the explainable score.

This trains a small logistic-regression model — pure Python, no numpy/sklearn,
so the project stays dependency-free — on the synthetic Metabase features to
predict a user's no-show propensity, then turns a pool's predicted attendance
into an *overbooking factor*: how many requests to admit to fill the physical
spaces in expectation (the airline trick).

Why it composes instead of corrupts:

- It reads the SAME features the rest of Newton 3 uses but writes NOTHING back
  to the behaviour score. The score stays a pure, explainable fold; the model
  feeds *capacity*, not *ranking*. So a black-box prediction can never make an
  allocation unexplainable — every ranking decision is still the rules-based
  score, and overbooking only changes how many people that ranking admits.
- That separation is the whole point: the project exists to answer "allocation
  feels random / nobody tells me why." A learned ranking function would bring
  the opacity back. A learned *capacity* function does not.

Honesty notes (same spirit as analysis/impact.py):

- There is no per-booking ground truth in the dataset, so we use the empirical
  rate `unused_bookings_3mo / requests_3mo` as the training label, and we
  EXCLUDE `unused_bookings_3mo` and `used_rate_pct` from the features so the
  model can't read the label off its own numerator.
- This is a baseline to prove the shape, not a tuned production model. With a
  real event log (which `newton.store` now captures) you would retrain on
  actual booking outcomes.

Run from the repository root:

    python -m analysis.predict
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "docs/artifacts/Algorithm User Complaints - Metabase.csv"

# Features that do not encode the label. nudge_offences correlates with
# no-shows (a legitimate signal); approval/rejection/volume describe demand.
FEATURES = (
    "approval_rate_pct",
    "rejection_rate_pct",
    "requests_3mo",
    "rejected_3mo",
    "nudge_offences_3mo",
)


@dataclass(frozen=True)
class Model:
    """A trained logistic-regression no-show predictor. `predict` takes a raw
    feature vector (same order as FEATURES) and returns P(no-show) in [0, 1].
    """

    weights: tuple[float, ...]
    bias: float
    means: tuple[float, ...]
    stds: tuple[float, ...]
    features: tuple[str, ...]

    def predict(self, raw: list[float]) -> float:
        z = self.bias + sum(
            w * (x - m) / s
            for w, x, m, s in zip(self.weights, raw, self.means, self.stds)
        )
        return _sigmoid(z)


def _sigmoid(z: float) -> float:
    if z < 0:  # numerically stable both ways
        e = math.exp(z)
        return e / (1.0 + e)
    return 1.0 / (1.0 + math.exp(-z))


def _num(value: str | None) -> float:
    try:
        return float((value or "").strip())
    except ValueError:
        return 0.0


def load(path: Path = CSV) -> list[tuple[list[float], float]]:
    """(raw feature vector, empirical no-show rate) per user with demand."""
    rows = []
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            requests = _num(r.get("requests_3mo"))
            if requests <= 0:
                continue  # no demand -> no no-show rate to learn from
            unused = _num(r.get("unused_bookings_3mo"))
            label = min(1.0, max(0.0, unused / requests))
            features = [_num(r.get(k)) for k in FEATURES]
            rows.append((features, label))
    return rows


def train(
    rows: list[tuple[list[float], float]],
    *,
    epochs: int = 400,
    lr: float = 0.5,
    l2: float = 1e-3,
) -> Model:
    """Fit logistic regression by full-batch gradient descent on cross-entropy.

    The label is a fractional rate in [0, 1]; cross-entropy handles that
    directly (the gradient is the same `x * (pred - y)` as for binary labels).
    Features are standardized so one learning rate fits every column.
    """
    dim = len(FEATURES)
    n = len(rows)
    means = [mean(x[j] for x, _ in rows) for j in range(dim)]
    stds = [
        math.sqrt(mean((x[j] - means[j]) ** 2 for x, _ in rows)) or 1.0
        for j in range(dim)
    ]
    std_rows = [
        ([(x[j] - means[j]) / stds[j] for j in range(dim)], y) for x, y in rows
    ]

    w = [0.0] * dim
    b = 0.0
    for _ in range(epochs):
        gw = [0.0] * dim
        gb = 0.0
        for x, y in std_rows:
            err = _sigmoid(b + sum(w[j] * x[j] for j in range(dim))) - y
            for j in range(dim):
                gw[j] += err * x[j]
            gb += err
        for j in range(dim):
            w[j] -= lr * (gw[j] / n + l2 * w[j])
        b -= lr * (gb / n)

    return Model(tuple(w), b, tuple(means), tuple(stds), FEATURES)


def mae(model: Model, rows: list[tuple[list[float], float]]) -> float:
    """Mean absolute error of predicted vs empirical no-show rate."""
    return mean(abs(model.predict(x) - y) for x, y in rows)


def overbooking_factor(probs: list[float]) -> float:
    """Requests-per-space multiplier: 1 / expected attendance rate.

    Expected attendance rate is mean(1 - p). To fill `spaces` seats in
    expectation, admit `round(spaces * overbooking_factor(probs))` requests.
    """
    attendance = mean(1.0 - p for p in probs)
    return 1.0 / attendance if attendance > 0 else 1.0


def _report(rows: list[tuple[list[float], float]]) -> str:
    model = train(rows)
    baseline = mean(y for _x, y in rows)  # predict the global mean
    model_mae = mae(model, rows)
    base_mae = mean(abs(baseline - y) for _x, y in rows)
    lift = 100 * (1 - model_mae / base_mae) if base_mae else 0.0

    probs = [model.predict(x) for x, _ in rows]
    factor = overbooking_factor(probs)
    spaces = 80
    admit = round(spaces * factor)

    weights = sorted(
        zip(model.features, model.weights), key=lambda kv: -abs(kv[1])
    )

    lines = [
        "# Predictive no-show — ML stretch (composed, not score-coupled)",
        "",
        f"Trained on {len(rows)} users from "
        "`docs/artifacts/…Metabase.csv`. Label = empirical no-show rate "
        "`unused_bookings_3mo / requests_3mo`; features exclude it to avoid "
        "leakage. Pure-Python logistic regression, no dependencies. Method + "
        "caveats: see the `analysis/predict.py` docstring.",
        "",
        "## Fit",
        "",
        f"- Mean absolute error: **{model_mae:.3f}** vs a predict-the-mean "
        f"baseline of **{base_mae:.3f}** — a **{lift:.0f}%** reduction.",
        f"- Mean predicted no-show rate: **{mean(probs):.1%}** "
        f"(empirical **{baseline:.1%}**) — calibrated, not just ranked.",
        "",
        "## What the model learned (standardized weights, |largest| first)",
        "",
        "| Feature | weight | direction |",
        "|---|---|---|",
    ]
    for name, w in weights:
        direction = "↑ more no-shows" if w > 0 else "↓ fewer no-shows"
        lines.append(f"| `{name}` | {w:+.2f} | {direction} |")

    lines += [
        "",
        "## Using it — overbooking, the airline trick",
        "",
        f"Across this pool the model predicts a mean attendance rate of "
        f"**{(1 / factor):.0%}**, an overbooking factor of **{factor:.2f}×**. "
        f"So to fill **{spaces}** physical spaces in expectation you would "
        f"admit **{admit}** requests — the ranking still decides *who*, the "
        "model only decides *how many*.",
        "",
        "## Why this composes with the score",
        "",
        "- The behaviour score (`newton.engine`) is untouched: it stays a "
        "pure, explainable fold. This model reads the same features but writes "
        "nothing back to it.",
        "- The model feeds **capacity**, not **ranking** — so it can never make "
        "an allocation unexplainable. Every rejection still cites the "
        "rules-based score (proposal #8); overbooking only changes how many of "
        "the ranked users are admitted.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    print(_report(load()))


if __name__ == "__main__":
    main()
