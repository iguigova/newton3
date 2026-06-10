"""The whole brain: the behaviour score as a pure fold over an event log.

`score(events, config, now)` is a deterministic function of its inputs. There
is no stored score to reset and no decay job to run — decay is computed here,
at read time. Events past their window contribute nothing and are dropped,
so the fold only ever touches a small, recent slice of the log.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from datetime import datetime

from newton.config import Config
from newton.models import Breakdown, Event, EventType, Impact, Tier


def evaluate(
    events: Iterable[Event], config: Config, *, now: datetime
) -> Breakdown:
    """Fold an event log into an explainable score at a point in time."""
    _require_aware(now)
    active = _dedup(sorted(_active(events, config, now=now), key=_at))
    impacts = _impacts(active, config, now=now)
    rewards = sum(i.points for i in impacts if i.points > 0)
    penalties = sum(i.points for i in impacts if i.points < 0)
    cap_adjustment = min(rewards, config.reward_cap) - rewards
    raw = config.base + rewards + cap_adjustment + penalties
    score_ = max(_round_half_up(raw), config.floor)
    return Breakdown(
        score=score_,
        tier=tier(score_, config),
        impacts=tuple(impacts),
        reward_cap_adjustment=cap_adjustment,
    )


def score(events: Iterable[Event], config: Config, *, now: datetime) -> int:
    """The behaviour score: the fold's bottom line."""
    return evaluate(events, config, now=now).score


def tier(value: int, config: Config) -> Tier:
    """Map a score onto its user-facing tier."""
    for floor, name in config.tiers:
        if value >= floor:
            return name
    return config.tiers[-1][1]


def is_force_last(
    events: Iterable[Event], config: Config, *, now: datetime
) -> bool:
    """Whether a user is force-ranked last (proposal #1).

    A count threshold, not a decay: `offence_override` offences within
    `offence_override_window_days` push the user behind everyone else,
    bypassing admin priority and behaviour score. Disabled when the
    threshold is unset.
    """
    if config.offence_override is None:
        return False
    _require_aware(now)
    window = config.offence_override_window_days
    offences = _dedup(
        [
            e
            for e in events
            if e.type is EventType.OFFENCE and _elapsed_days(e, now) < window
        ]
    )
    return len(offences) >= config.offence_override


def _round_half_up(value: float) -> int:
    """Round to the nearest integer, ties going up.

    Python's built-in `round` is round-half-to-even (banker's), so 92.5
    becomes 92 but 97.5 becomes 98 — equal-magnitude changes rounding in
    different directions. A behaviour score a user can audit must round
    predictably, so ties always go up.
    """
    return math.floor(value + 0.5)


def _require_aware(now: datetime) -> None:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")


def _at(event: Event) -> datetime:
    return event.at


def _dedup(events: list[Event]) -> list[Event]:
    """Drop redelivered events: a repeated `event_id` is counted once."""
    seen: set[str] = set()
    out = []
    for e in events:
        if e.event_id is not None and e.event_id in seen:
            continue
        if e.event_id is not None:
            seen.add(e.event_id)
        out.append(e)
    return out


def _active(
    events: Iterable[Event], config: Config, *, now: datetime
) -> list[Event]:
    """Enabled, non-expired events — the only ones that move the score."""
    return [
        e
        for e in events
        if e.type in config.weights
        and _elapsed_days(e, now) < config.window_days(e.type)
    ]


def _impacts(
    events: list[Event], config: Config, *, now: datetime
) -> list[Impact]:
    """Per-event contributions, with repeat penalties escalating in time."""
    seen: Counter[EventType] = Counter()
    impacts = []
    for e in events:
        points = _contribution(e, config, now=now, prior=seen[e.type])
        if config.weight(e.type) < 0:
            seen[e.type] += 1
        impacts.append(Impact(type=e.type, at=e.at, points=points))
    return impacts


def _contribution(
    event: Event, config: Config, *, now: datetime, prior: int
) -> float:
    """A single event's decayed, escalation-adjusted point value."""
    decayed = config.weight(event.type) * _remaining(event, config, now=now)
    if config.weight(event.type) < 0:
        return decayed * (1 + config.escalation * prior)
    return decayed


def _remaining(event: Event, config: Config, *, now: datetime) -> float:
    """Fraction of an event's weight still in effect (linear decay).

    Clamped to [0, 1]: a future-dated event (clock skew) counts at full
    weight, never more, and a past-window event counts as zero.
    """
    window = config.window_days(event.type)
    return min(1.0, max(0.0, 1 - _elapsed_days(event, now) / window))


def _elapsed_days(event: Event, now: datetime) -> float:
    return (now - event.at).total_seconds() / 86400
