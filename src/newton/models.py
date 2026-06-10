"""Value objects for Newton 3. All immutable; the engine never mutates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EventType(Enum):
    """Scoring-relevant events. Anything else is ignored by the fold.

    `EARLY_RELEASE` is a positive signal — releasing a booking early enough
    for someone else to use the space. The brief lists it as `booking.cancelled
    → +5 if early cancel — TBD`; it ships disabled (absent from
    `DEFAULT_WEIGHTS`) and a tenant enables it by adding a weight + window. It
    exists so behaviour standing can be *earned*, not only lost — carpool is
    otherwise the only way up, and most users have no carpool option.
    """

    NO_SHOW = "unused_booking"
    FREE_SPACE = "free_space_used"
    OFFENCE = "offence"
    CARPOOL = "carpool"
    EARLY_RELEASE = "booking_cancelled_early"


class Tier(Enum):
    PLATINUM = "Platinum"
    GOLD = "Gold"
    SILVER = "Silver"
    BRONZE = "Bronze"
    RESTRICTED = "Restricted"


@dataclass(frozen=True, slots=True)
class Event:
    """One entry in the append-only behaviour log. `at` is timezone-aware.

    `event_id` is the idempotency key: under at-least-once delivery a
    redelivered event carries the same id and the fold counts it once.
    """

    user_id: str
    type: EventType
    at: datetime
    event_id: str | None = None


@dataclass(frozen=True, slots=True)
class Impact:
    """An event's contribution to the score, evaluated at a point in time."""

    type: EventType
    at: datetime
    points: float


@dataclass(frozen=True, slots=True)
class Breakdown:
    """The explainable result of the fold — the GDPR 'recent impacts' view.

    The arithmetic reconciles by construction:
    `base + sum(impacts) + reward_cap_adjustment`, then floored, equals
    `score`. The adjustment is <= 0, non-zero only when the cap bites.
    """

    score: int
    tier: Tier
    impacts: tuple[Impact, ...]
    reward_cap_adjustment: float


@dataclass(frozen=True, slots=True)
class Candidate:
    """A user up for allocation, with their resolved priority layers.

    `force_last` (proposal #1) ranks the user behind everyone, regardless of
    admin priority or behaviour score — the offence override, distinct from the
    user-facing `Tier.RESTRICTED` score band.
    """

    user_id: str
    group_priority: int
    user_priority: int
    score: int
    force_last: bool = False


@dataclass(frozen=True, slots=True)
class Decision:
    """An allocation outcome with its rationale (proposal #8)."""

    user_id: str
    allocated: bool
    rank: int  # 0-based position in the ranking
    reason: str
