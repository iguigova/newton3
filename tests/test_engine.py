from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from newton.config import DEFAULT_WEIGHTS, DEFAULT_WINDOWS, Config
from newton.engine import evaluate, is_force_last, score, tier
from newton.models import Event, EventType, Tier

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def ev(type: EventType, days_ago: float) -> Event:
    return Event("u", type, NOW - timedelta(days=days_ago))


def test_empty_log_is_base_score():
    assert score([], Config(), now=NOW) == 100


def test_fresh_offence_applies_full_weight():
    assert score([ev(EventType.OFFENCE, 0)], Config(), now=NOW) == 95


def test_penalty_decays_linearly_over_window():
    # offence -5 over a 28-day window; 21 days in -> a quarter remains.
    result = evaluate([ev(EventType.OFFENCE, 21)], Config(), now=NOW)
    assert result.impacts[0].points == pytest.approx(-1.25)
    assert result.score == 99


def test_event_past_window_drops_out():
    assert score([ev(EventType.OFFENCE, 28)], Config(), now=NOW) == 100
    assert score([ev(EventType.OFFENCE, 40)], Config(), now=NOW) == 100


def test_rewards_are_capped():
    events = [ev(EventType.CARPOOL, 0) for _ in range(10)]
    result = evaluate(events, Config(), now=NOW)
    assert result.score == 120  # base 100 + min(50, cap 20)
    assert result.reward_cap_adjustment == -30  # 20 cap - 50 raw


def test_breakdown_arithmetic_reconciles_under_cap():
    events = [ev(EventType.CARPOOL, 0) for _ in range(10)]
    result = evaluate(events, Config(), now=NOW)
    shown = sum(i.points for i in result.impacts)
    reconciled = 100 + shown + result.reward_cap_adjustment
    assert round(reconciled) == result.score


def test_future_event_counts_at_full_weight_not_more():
    # clock skew: an event 10 days ahead must not amplify past full weight
    assert score([ev(EventType.OFFENCE, -10)], Config(), now=NOW) == 95


def test_redelivered_event_is_counted_once():
    once = Event("u", EventType.OFFENCE, NOW, event_id="evt-1")
    twice = [once, Event("u", EventType.OFFENCE, NOW, event_id="evt-1")]
    assert score(twice, Config(), now=NOW) == 95  # not 90


def test_events_without_id_are_not_deduplicated():
    # distinct real events that happen to coincide still both count
    pair = [ev(EventType.OFFENCE, 0), ev(EventType.OFFENCE, 0)]
    assert score(pair, Config(), now=NOW) == 90


def test_naive_now_is_rejected():
    naive = datetime(2026, 6, 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        score([], Config(), now=naive)


def test_score_rounds_half_up_not_banker():
    # three fresh no-shows, escalation 0.5 -> -3, -4.5, -6 = -13.5 -> 86.5.
    # Half-up gives 87; Python's round() (banker's) would give 86.
    events = [ev(EventType.NO_SHOW, 0) for _ in range(3)]
    assert score(events, Config(escalation=0.5), now=NOW) == 87


def test_score_never_below_floor():
    events = [ev(EventType.OFFENCE, 0) for _ in range(30)]
    assert score(events, Config(), now=NOW) == 0


def test_escalation_increases_repeat_penalties():
    events = [ev(EventType.NO_SHOW, 0) for _ in range(2)]
    # -3, then -3 * (1 + 0.5) -> total -7.5 -> 92.5, rounded half-up to 93.
    assert score(events, Config(escalation=0.5), now=NOW) == 93


def test_escalation_applies_to_the_newer_repeat_not_the_older():
    # Events are folded oldest-first: the oldest repeat carries prior=0 (no
    # escalation), the fresh one escalates. Decay distinguishes the order:
    # fresh -3*(1+1.0) = -6; the 6-day-old one -3*(1/7) ~ -0.43 -> ~94.
    events = [ev(EventType.NO_SHOW, 0), ev(EventType.NO_SHOW, 6)]
    assert score(events, Config(escalation=1.0), now=NOW) == 94


def test_positive_signals_never_escalate():
    # escalation is for repeat *penalties*; repeat rewards stay linear.
    cfg = Config(escalation=1.0)
    events = [ev(EventType.CARPOOL, 0) for _ in range(2)]
    assert score(events, cfg, now=NOW) == 110  # 100 + 5 + 5, not amplified


def test_early_release_is_disabled_by_default():
    # ships absent from DEFAULT_WEIGHTS, so it is inert until a tenant opts in.
    assert score([ev(EventType.EARLY_RELEASE, 0)], Config(), now=NOW) == 100


def test_tenant_can_enable_early_release_to_earn_standing():
    # the config-enabled path *up*: a no-show offset by two early releases.
    cfg = Config(
        weights={**DEFAULT_WEIGHTS, EventType.EARLY_RELEASE: 5},
        windows={**DEFAULT_WINDOWS, EventType.EARLY_RELEASE: 14},
    )
    events = [
        ev(EventType.NO_SHOW, 0),
        ev(EventType.EARLY_RELEASE, 0),
        ev(EventType.EARLY_RELEASE, 0),
    ]
    assert score(events, cfg, now=NOW) == 107  # 100 - 3 + 10


def test_disabled_event_is_ignored():
    config = Config(weights={EventType.OFFENCE: -5})
    assert score([ev(EventType.CARPOOL, 0)], config, now=NOW) == 100


def test_offence_override_marks_repeat_offenders():
    config = Config(offence_override=2)
    events = [ev(EventType.OFFENCE, 1), ev(EventType.OFFENCE, 2)]
    assert is_force_last(events, config, now=NOW)


def test_offence_override_is_off_by_default():
    events = [ev(EventType.OFFENCE, 1) for _ in range(5)]
    assert not is_force_last(events, Config(), now=NOW)


def test_offence_override_ignores_offences_outside_its_window():
    config = Config(offence_override=2, offence_override_window_days=30)
    events = [ev(EventType.OFFENCE, 5), ev(EventType.OFFENCE, 40)]
    assert not is_force_last(events, config, now=NOW)


@pytest.mark.parametrize(
    "value,expected",
    [
        (200, Tier.PLATINUM),
        (130, Tier.GOLD),
        (100, Tier.SILVER),
        (60, Tier.BRONZE),
        (10, Tier.RESTRICTED),
    ],
)
def test_tier_mapping(value, expected):
    assert tier(value, Config()) == expected
