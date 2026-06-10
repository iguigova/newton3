"""Append-only event log. In memory now; the DynamoDB target fits the same
Protocol, so nothing above this layer changes when it swaps in.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from newton.config import Config
from newton.models import Event


class EventStore(Protocol):
    """The DynamoDB behavior-events table satisfies this structurally."""

    def append(self, event: Event) -> None: ...

    def events(self, user_id: str) -> list[Event]: ...


class InMemoryStore:
    """Prototype store with the same interface as the DynamoDB target."""

    def __init__(self) -> None:
        self._log: dict[str, list[Event]] = defaultdict(list)

    def append(self, event: Event) -> None:
        self._log[event.user_id].append(event)

    def events(self, user_id: str) -> list[Event]:
        return list(self._log[user_id])

    def extend(self, events: Iterable[Event]) -> None:
        for event in events:
            self.append(event)

    def compact(self, config: Config, *, now: datetime) -> int:
        """Drop events past their window — they can't affect any score.

        Returns the number removed; the log stays bounded rather than
        growing with history.
        """
        removed = 0
        for user_id, log in self._log.items():
            kept = [e for e in log if _within_window(e, config, now)]
            removed += len(log) - len(kept)
            self._log[user_id] = kept
        return removed


def _within_window(event: Event, config: Config, now: datetime) -> bool:
    if event.type not in config.windows:
        return True
    elapsed = (now - event.at).total_seconds() / 86400
    return elapsed < config.window_days(event.type)
