"""Event-stream simulator. The only place that reads the clock; the engine
stays pure by taking `now` as an argument.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone

from newton.allocate import decide, rank, to_candidate
from newton.api import behavior_score
from newton.config import Config
from newton.models import Event, EventType
from newton.observability import log_allocation
from newton.store import InMemoryStore


class _AuditFormatter(logging.Formatter):
    """Surface the structured audit payload a JSON handler would emit."""

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        payload = getattr(record, "newton", None)
        return f"{line} {json.dumps(payload)}" if payload else line


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_AuditFormatter("audit %(name)s %(message)s"))
    logging.getLogger("newton").handlers = [handler]
    logging.getLogger("newton").setLevel(logging.INFO)


def _demo(now: datetime) -> None:
    config = Config(offence_override=2)  # 2 offences / 30d -> ranked last
    store = InMemoryStore()
    day = timedelta(days=1)

    # A recovering carpooler, a recovering one-offence user, and a repeat
    # offender who trips the override.
    store.extend(
        [
            Event("alice", EventType.NO_SHOW, now - 20 * day),
            Event("alice", EventType.OFFENCE, now - 10 * day),
            Event("bob", EventType.CARPOOL, now - 3 * day),
            Event("bob", EventType.NO_SHOW, now - 1 * day),
            Event("carol", EventType.OFFENCE, now - 5 * day),
            Event("carol", EventType.OFFENCE, now - 4 * day),
            Event("carol", EventType.OFFENCE, now - 2 * day),
        ]
    )

    users = ["alice", "bob", "carol"]
    candidates = [
        to_candidate(u, store.events(u), config, now=now) for u in users
    ]
    ranked = rank(candidates)
    log_allocation(ranked, config, now=now)

    print("Ranking (best first):")
    for c in ranked:
        flag = "  [ranked last: repeat offences]" if c.force_last else ""
        print(f"  {c.user_id:<6} score={c.score}{flag}")

    print("\nAllocation with 1 space — who is allocated, and why:")
    for d in decide(candidates, capacity=1):
        verdict = "ALLOCATED" if d.allocated else "rejected "
        print(f"  {d.user_id:<6} {verdict}  {d.reason}")

    print("\nbob's behaviour-score API response:")
    print(json.dumps(behavior_score(store, config, "bob", now=now), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="newton")
    parser.add_argument("command", choices=["demo"])
    parser.parse_args()
    _configure_logging()
    _demo(datetime.now(timezone.utc))


if __name__ == "__main__":
    main()
