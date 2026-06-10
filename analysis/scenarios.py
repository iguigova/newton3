"""Edge-case studies and demo runs — synthetic, deterministic scenarios that
exercise the scoring engine's corners as a readable walkthrough for the demo.
Run from the repository root:

    python -m analysis.scenarios
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from newton.config import Config
from newton.engine import evaluate, score, tier
from newton.models import Event, EventType

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def ev(kind: EventType, days_ago: float) -> Event:
    return Event("u", kind, NOW - days_ago * DAY)


def row(label: str, value: object) -> None:
    print(f"  {label:<42} {value}")


def decay_curve() -> None:
    print("\n[decay] one offence (-5) recovers linearly over its 28d window")
    cfg = Config()
    for d in (0, 7, 14, 21, 28):
        result = evaluate([ev(EventType.OFFENCE, d)], cfg, now=NOW)
        penalty = result.impacts[0].points if result.impacts else 0.0
        # The exact penalty shrinks by 1.25/week; the integer score is that
        # value rounded, so the printed steps look uneven though decay is linear.
        row(
            f"score {d:>2}d after the offence",
            f"{result.score:>3}   (penalty {penalty:+.2f})",
        )


def per_event_decay() -> None:
    print("\n[per-event decay] each penalty fades on its own timer")
    cfg = Config()
    both_recent = [ev(EventType.OFFENCE, 7), ev(EventType.OFFENCE, 7)]
    one_old = [ev(EventType.OFFENCE, 7), ev(EventType.OFFENCE, 21)]
    row("two offences, both 7d ago", score(both_recent, cfg, now=NOW))
    row("one 7d ago, one 21d ago", score(one_old, cfg, now=NOW))
    print("  -> the older penalty contributes less; no global-timer reset")


def escalation() -> None:
    print("\n[escalation] repeat offences may escalate by tenant policy")
    evs = [ev(EventType.NO_SHOW, 0) for _ in range(3)]
    row("3 fresh no-shows, escalation off", score(evs, Config(), now=NOW))
    row(
        "3 fresh no-shows, escalation 0.5",
        score(evs, Config(escalation=0.5), now=NOW),
    )


def reward_cap() -> None:
    print("\n[reward cap] rewards saturate at +20 over the rolling window")
    five = [ev(EventType.CARPOOL, 0) for _ in range(5)]
    ten = [ev(EventType.CARPOOL, 0) for _ in range(10)]
    row("5 carpools (+25 raw)", score(five, Config(), now=NOW))
    row("10 carpools (+50 raw)", score(ten, Config(), now=NOW))


def floor_and_skew() -> None:
    print("\n[floor + clock skew] hard floor at 0; future events clamp")
    many = [ev(EventType.OFFENCE, 0) for _ in range(40)]
    row("40 fresh offences (-200 raw)", score(many, Config(), now=NOW))
    row(
        "offence dated 10d in the future",
        score([ev(EventType.OFFENCE, -10)], Config(), now=NOW),
    )


def explainability() -> None:
    print("\n[explainability] the shown trace reconciles to the score")
    result = evaluate(
        [ev(EventType.CARPOOL, 0) for _ in range(10)], Config(), now=NOW
    )
    shown = sum(i.points for i in result.impacts)
    row("sum of shown impacts", shown)
    row("reward-cap adjustment", result.reward_cap_adjustment)
    row(
        "100 + impacts + adjustment",
        round(100 + shown + result.reward_cap_adjustment),
    )
    row("reported score", result.score)


def tiers() -> None:
    print("\n[tiers] score -> tier at the documented thresholds")
    for value in (200, 130, 100, 60, 10):
        row(f"score {value:>3}", tier(value, Config()).value)


def main() -> None:
    for scenario in (
        decay_curve,
        per_event_decay,
        escalation,
        reward_cap,
        floor_and_skew,
        explainability,
        tiers,
    ):
        scenario()


if __name__ == "__main__":
    main()
