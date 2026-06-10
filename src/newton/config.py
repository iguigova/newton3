"""Per-tenant scoring policy. Defaults reproduce the documented spec.

Everything the review flagged as 'hardcoded' lives here and is overridable:
point values, decay windows, reward cap, escalation, tiers, and which events
are enabled (an event absent from `weights` is disabled).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from newton.models import EventType, Tier

# Behaviour Scoring System point values.
DEFAULT_WEIGHTS: dict[EventType, int] = {
    EventType.NO_SHOW: -3,
    EventType.FREE_SPACE: -1,
    EventType.OFFENCE: -5,
    EventType.CARPOOL: 5,
}

# Horizon per event, in days. A contribution fades linearly to zero across
# its window, then drops out of the fold — which bounds the working set.
DEFAULT_WINDOWS: dict[EventType, int] = {
    EventType.NO_SHOW: 7,  # one allocation cycle
    EventType.FREE_SPACE: 14,  # 2 weeks
    EventType.OFFENCE: 28,  # 4 weeks
    EventType.CARPOOL: 28,  # rolls off with the reward window
}

# Tier floors, highest first; score >= floor selects the tier.
DEFAULT_TIERS: tuple[tuple[int, Tier], ...] = (
    (150, Tier.PLATINUM),
    (120, Tier.GOLD),
    (80, Tier.SILVER),
    (50, Tier.BRONZE),
    (0, Tier.RESTRICTED),
)


@dataclass(frozen=True, slots=True)
class Config:
    """A tenant's scoring policy."""

    version: str = "default"  # tenant policy identity, for traceability
    base: int = 100
    floor: int = 0
    reward_cap: int = 20
    escalation: float = 0.0  # >0 escalates repeat penalties of one type
    offence_override: int | None = None  # N offences in window -> forced last
    offence_override_window_days: int = 30
    weights: dict[EventType, int] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS)
    )
    windows: dict[EventType, int] = field(
        default_factory=lambda: dict(DEFAULT_WINDOWS)
    )
    tiers: tuple[tuple[int, Tier], ...] = DEFAULT_TIERS

    def __post_init__(self) -> None:
        if min(self.base, self.floor, self.reward_cap, self.escalation) < 0:
            raise ValueError("base/floor/reward_cap/escalation must be >= 0")
        missing = [e for e in self.weights if e not in self.windows]
        if missing:
            raise ValueError(f"enabled events lack a window: {missing}")
        non_positive = [e for e, d in self.windows.items() if d <= 0]
        if non_positive:
            raise ValueError(f"windows must be positive: {non_positive}")
        floors = [floor for floor, _ in self.tiers]
        if floors != sorted(floors, reverse=True):
            raise ValueError("tiers must be ordered by descending floor")
        if self.offence_override is not None and self.offence_override < 1:
            raise ValueError("offence_override must be >= 1 when set")
        if self.offence_override_window_days <= 0:
            raise ValueError("offence_override_window_days must be positive")

    def weight(self, event_type: EventType) -> int:
        return self.weights[event_type]

    def window_days(self, event_type: EventType) -> int:
        return self.windows[event_type]
