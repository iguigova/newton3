"""Allocation ranking and explainable outcomes.

The behaviour score is the third priority layer; a force-last user (proposal
#1, the offence override) is ranked behind everyone. `decide` turns a ranking +
capacity into per-user outcomes with a rationale (proposal #8).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from newton.config import Config
from newton.engine import is_force_last, score
from newton.models import Candidate, Decision, Event


def rank(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Order users for allocation: force-last, group, user, then behaviour.

    Layers 1-2 are admin-controlled; layer 3 is the behaviour score (higher
    is better). Force-last users sort last regardless. The sort is stable,
    so equal keys keep input order — pass a shuffled input for the spec's
    random tie-break.
    """
    return sorted(candidates, key=_key)


def _key(c: Candidate) -> tuple[bool, int, int, int]:
    return (c.force_last, c.group_priority, c.user_priority, -c.score)


def gsi_sort_key(c: Candidate, *, width: int = 4) -> str:
    """Pack the sort key into one ascending-sortable DynamoDB GSI key.

    DynamoDB sort keys are ascending only; inverting the score makes
    ascending order equal best-first, so a single Query returns a group
    already ranked. The leading force-last flag sorts offence-override users
    behind everyone.

    Contract: `group_priority`, `user_priority`, and `score` must each be
    in `[0, 10**width)`. Negative or oversized fields break the fixed-width
    zero-padding the lexicographic order relies on, so they are rejected
    rather than mis-sorted. Default `width=4` admits values 0..9999.
    """
    ceiling = 10**width
    fields = {
        "group_priority": c.group_priority,
        "user_priority": c.user_priority,
        "score": c.score,
    }
    out_of_range = {k: v for k, v in fields.items() if not 0 <= v < ceiling}
    if out_of_range:
        raise ValueError(
            f"gsi_sort_key fields must be in [0, {ceiling}) for width="
            f"{width}; out of range: {out_of_range}"
        )
    inverted = ceiling - 1 - c.score
    return (
        f"{int(c.force_last)}#"
        f"{c.group_priority:0{width}d}#"
        f"{c.user_priority:0{width}d}#"
        f"{inverted:0{width}d}"
    )


def to_candidate(
    user_id: str,
    events: Iterable[Event],
    config: Config,
    *,
    now: datetime,
    group_priority: int = 0,
    user_priority: int = 0,
) -> Candidate:
    """Build a Candidate from a user's event log: score + restriction."""
    log = list(events)
    return Candidate(
        user_id=user_id,
        group_priority=group_priority,
        user_priority=user_priority,
        score=score(log, config, now=now),
        force_last=is_force_last(log, config, now=now),
    )


def decide(
    candidates: Iterable[Candidate], *, capacity: int
) -> list[Decision]:
    """Rank, allocate the top `capacity`, and attach a reason to each."""
    ranked = rank(candidates)
    return [
        Decision(c.user_id, i < capacity, i, _reason(c, i, ranked, capacity))
        for i, c in enumerate(ranked)
    ]


def _reason(
    c: Candidate, rank_: int, ranked: list[Candidate], capacity: int
) -> str:
    if rank_ < capacity:
        return "allocated"
    if c.force_last:
        return "ranked last by the offence override — repeat offences"
    if capacity <= 0:
        return "no spaces were available"
    marginal = ranked[capacity - 1]
    above = (marginal.group_priority, marginal.user_priority)
    if (c.group_priority, c.user_priority) > above:
        return f"{capacity} users with higher admin priority filled the spaces"
    if c.score == marginal.score:
        return (
            f"within your priority bracket and tied on behaviour score "
            f"({c.score}); the tie-break decided the last space"
        )
    return (
        f"within your priority bracket; a behaviour score of {marginal.score} "
        f"was allocated and you have {c.score}"
    )
