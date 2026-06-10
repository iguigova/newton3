from __future__ import annotations

import pytest

from newton.config import Config
from newton.models import EventType


def test_enabled_event_without_window_is_rejected():
    with pytest.raises(ValueError, match="lack a window"):
        Config(weights={EventType.CARPOOL: 5}, windows={})


def test_non_positive_window_is_rejected():
    with pytest.raises(ValueError, match="must be positive"):
        Config(windows={**Config().windows, EventType.OFFENCE: 0})


def test_negative_policy_value_is_rejected():
    with pytest.raises(ValueError):
        Config(reward_cap=-1)


def test_unsorted_tiers_are_rejected():
    from newton.models import Tier

    with pytest.raises(ValueError, match="descending"):
        Config(tiers=((80, Tier.SILVER), (150, Tier.PLATINUM)))
