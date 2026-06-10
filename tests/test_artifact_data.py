"""Tests driven by the anonymized artifact dataset under `docs/artifacts/`.
Skipped automatically if the CSV is not present, so the suite still runs on a
clean checkout.
"""

from __future__ import annotations

from statistics import mean

import pytest

from analysis.impact import (
    CSV,
    LONG_MEMORY,
    by_underserved_tier,
    load,
    score_rows,
)

pytestmark = pytest.mark.skipif(
    not CSV.exists(), reason="artifact CSV not present"
)


def test_loads_the_expected_population():
    assert 1100 < len(load()) < 1300  # ~1200 synthetic users carry a user_id


def test_penalty_only_scores_stay_within_bounds():
    scored = score_rows(load(), LONG_MEMORY)
    assert all(0 <= score <= 100 for _u, _l, score, _p in scored)


def test_behaviour_layer_separates_abuse_from_underserved():
    # The central business claim: under a long-memory profile the high-demand
    # underserved (A/B/C) score better than the multi-misser tier (M).
    tiers = by_underserved_tier(score_rows(load(), LONG_MEMORY))
    underserved = mean(tiers["A"] + tiers["B"] + tiers["C"])
    multi_misser = mean(tiers["M"])
    assert underserved > multi_misser
