"""Tests for the predictive no-show stretch. Skipped if the CSV is absent, so
the suite still runs on a clean checkout.
"""

from __future__ import annotations

from statistics import mean

import pytest

from analysis.predict import (
    CSV,
    FEATURES,
    load,
    mae,
    overbooking_factor,
    train,
)

pytestmark = pytest.mark.skipif(
    not CSV.exists(), reason="artifact CSV not present"
)


def test_model_beats_the_predict_the_mean_baseline():
    rows = load()
    model = train(rows)
    baseline = mean(y for _x, y in rows)
    base_mae = mean(abs(baseline - y) for _x, y in rows)
    assert mae(model, rows) < base_mae  # learned signal, not just the mean


def test_predictions_are_probabilities():
    rows = load()
    model = train(rows)
    assert all(0.0 <= model.predict(x) <= 1.0 for x, _ in rows)


def test_model_does_not_see_the_label_features():
    # leakage guard: the no-show numerator and used-rate must not be inputs.
    assert "unused_bookings_3mo" not in FEATURES
    assert "used_rate_pct" not in FEATURES


def test_overbooking_factor_admits_at_least_the_seats():
    # attendance <= 100%, so you always admit >= the physical spaces.
    rows = load()
    model = train(rows)
    probs = [model.predict(x) for x, _ in rows]
    assert overbooking_factor(probs) >= 1.0
