from __future__ import annotations

from datetime import datetime, timedelta, timezone

from newton.api import behavior_score
from newton.config import Config
from newton.models import Event, EventType
from newton.store import InMemoryStore

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_response_carries_score_and_traceability():
    store = InMemoryStore()
    store.append(Event("u", EventType.OFFENCE, NOW))
    resp = behavior_score(store, Config(version="tenant-1"), "u", now=NOW)
    assert resp["score"] == 95
    assert resp["tier"] == "Silver"
    assert resp["config_version"] == "tenant-1"
    assert resp["evaluated_at"] == NOW.isoformat()
    assert resp["recent_impacts"][0]["event"] == "offence"


def test_force_ranked_last_is_surfaced_for_repeat_offenders():
    # a user can sit in a healthy tier yet be ranked last by the override;
    # the score alone would not explain the rejection, so the API exposes it.
    store = InMemoryStore()
    store.extend(
        [
            Event("u", EventType.OFFENCE, NOW - timedelta(days=1)),
            Event("u", EventType.OFFENCE, NOW - timedelta(days=2)),
        ]
    )
    config = Config(offence_override=2, offence_override_window_days=30)
    resp = behavior_score(store, config, "u", now=NOW)
    assert resp["force_ranked_last"] is True
    assert resp["tier"] == "Silver"  # still a healthy score, yet ranked last


def test_force_ranked_last_is_false_when_override_disabled():
    store = InMemoryStore()
    store.append(Event("u", EventType.OFFENCE, NOW))
    assert behavior_score(store, Config(), "u", now=NOW)["force_ranked_last"] is False


def test_impacts_are_most_recent_first():
    store = InMemoryStore()
    store.extend(
        [
            Event("u", EventType.OFFENCE, NOW - timedelta(days=20)),
            Event("u", EventType.NO_SHOW, NOW - timedelta(days=2)),
        ]
    )
    resp = behavior_score(store, Config(), "u", now=NOW)
    ats = [impact["at"] for impact in resp["recent_impacts"]]
    assert ats == sorted(ats, reverse=True)
