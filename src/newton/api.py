"""The read API. One function, framework-free, returns a serializable dict."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from newton.allocate import decide
from newton.config import Config
from newton.engine import evaluate, is_force_last
from newton.models import Candidate
from newton.observability import log_evaluation
from newton.store import EventStore


def behavior_score(
    store: EventStore, config: Config, user_id: str, *, now: datetime
) -> dict[str, Any]:
    """Handler for GET /users/{id}/behavior-score.

    The response carries the live score and its impact trace, so the
    explainability surface (GDPR Art. 22) is the score's own trace.
    `force_ranked_last` exposes the offence override (proposal #1): a user can
    sit in a healthy tier yet still be ranked behind everyone, so the score
    alone would not explain a rejection — this surfaces it.
    `config_version` and `evaluated_at` make a response reproducible and
    auditable. Impacts are most-recent first.
    """
    events = store.events(user_id)
    result = evaluate(events, config, now=now)
    log_evaluation(user_id, result, config, now=now)
    return {
        "user_id": user_id,
        "score": result.score,
        "tier": result.tier.value,
        "force_ranked_last": is_force_last(events, config, now=now),
        "reward_cap_adjustment": round(result.reward_cap_adjustment, 2),
        "config_version": config.version,
        "evaluated_at": now.isoformat(),
        "recent_impacts": [
            {
                "event": i.type.value,
                "at": i.at.isoformat(),
                "points": round(i.points, 2),
            }
            for i in reversed(result.impacts)
        ],
    }


def allocation_report(
    candidates: Iterable[Candidate], *, capacity: int
) -> list[dict[str, Any]]:
    """Per-user allocation outcomes with rationale (proposal #8)."""
    return [
        {
            "user_id": d.user_id,
            "allocated": d.allocated,
            "rank": d.rank,
            "reason": d.reason,
        }
        for d in decide(candidates, capacity=capacity)
    ]
