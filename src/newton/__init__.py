"""Newton 3 — behaviour-driven allocation as a pure fold over an event log."""

from newton.allocate import decide, gsi_sort_key, rank, to_candidate
from newton.api import allocation_report, behavior_score
from newton.config import Config
from newton.engine import evaluate, is_force_last, score, tier
from newton.models import (
    Breakdown,
    Candidate,
    Decision,
    Event,
    EventType,
    Impact,
    Tier,
)
from newton.observability import log_allocation, log_evaluation
from newton.store import EventStore, InMemoryStore

__all__ = [
    "Breakdown",
    "Candidate",
    "Config",
    "Decision",
    "Event",
    "EventStore",
    "EventType",
    "Impact",
    "InMemoryStore",
    "Tier",
    "allocation_report",
    "behavior_score",
    "decide",
    "evaluate",
    "gsi_sort_key",
    "is_force_last",
    "log_allocation",
    "log_evaluation",
    "rank",
    "score",
    "tier",
    "to_candidate",
]
