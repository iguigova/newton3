from __future__ import annotations

from datetime import datetime, timedelta, timezone

from newton.config import Config
from newton.models import Event, EventType
from newton.store import InMemoryStore

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_append_and_read_round_trips():
    store = InMemoryStore()
    e = Event("u", EventType.OFFENCE, NOW)
    store.append(e)
    assert store.events("u") == [e]
    assert store.events("absent") == []  # no KeyError for unknown users


def test_compact_drops_events_past_their_window():
    store = InMemoryStore()
    live = Event("u", EventType.OFFENCE, NOW - timedelta(days=5))
    store.extend(
        [
            Event("u", EventType.OFFENCE, NOW - timedelta(days=40)),  # > 28d
            live,
        ]
    )
    removed = store.compact(Config(), now=NOW)
    assert removed == 1
    assert store.events("u") == [live]


def test_compact_keeps_event_types_without_a_window():
    # an event type absent from the config has no horizon, so it is never aged
    # out — compaction only bounds the types the score actually folds.
    store = InMemoryStore()
    cfg = Config(
        weights={EventType.OFFENCE: -5}, windows={EventType.OFFENCE: 28}
    )
    store.append(Event("u", EventType.CARPOOL, NOW - timedelta(days=999)))
    assert store.compact(cfg, now=NOW) == 0
    assert len(store.events("u")) == 1
