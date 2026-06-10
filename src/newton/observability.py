"""Structured audit logging for score and allocation decisions.

The pure engine emits no logs; these shells do, recording *what was decided,
under which policy version, and when* — the audit trail behind the
explainability surface. Records attach to the log record under `extra["newton"]`
so a JSON handler can emit them structured. The library configures no handler;
the application owns log routing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime

from newton.config import Config
from newton.models import Breakdown, Candidate

logger = logging.getLogger("newton")


def log_evaluation(
    user_id: str, breakdown: Breakdown, config: Config, *, now: datetime
) -> None:
    logger.info(
        "score.evaluated",
        extra={
            "newton": {
                "user_id": user_id,
                "score": breakdown.score,
                "tier": breakdown.tier.value,
                "events_considered": len(breakdown.impacts),
                "config_version": config.version,
                "evaluated_at": now.isoformat(),
            }
        },
    )


def log_allocation(
    ranked: Sequence[Candidate], config: Config, *, now: datetime
) -> None:
    logger.info(
        "allocation.ranked",
        extra={
            "newton": {
                "ranked": len(ranked),
                "top_ranked": [c.user_id for c in ranked[:10]],
                "config_version": config.version,
                "ranked_at": now.isoformat(),
            }
        },
    )
