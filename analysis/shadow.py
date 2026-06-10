"""Shadow-mode evaluation: compare the new behaviour ranking against a mock
legacy (priority-only) ranking.

The mock legacy stands in for production, where the comparator diffs against
real legacy output. Behaviour is layer 3 — a tie-break within an
admin-priority bracket — so measurement compares within brackets; a single
pooled ranking overstates movement, since admin priority dominates across
brackets.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence

from newton.allocate import rank
from newton.models import Candidate


def legacy_rank(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Admin priority layers only, no behaviour. Stable, so an equal-priority
    bracket keeps input order — behaviour is the one thing Newton 3 adds.
    """
    return sorted(
        candidates, key=lambda c: (c.group_priority, c.user_priority)
    )


def brackets(
    candidates: Iterable[Candidate],
) -> dict[tuple[int, int], list[Candidate]]:
    """Group users by identical admin priority — the bracket within which the
    behaviour score is the sole differentiator (the legacy tie-break).
    """
    out: dict[tuple[int, int], list[Candidate]] = defaultdict(list)
    for c in candidates:
        out[(c.group_priority, c.user_priority)].append(c)
    return dict(out)


def rank_changes(
    candidates: Iterable[Candidate],
) -> list[tuple[str, int, int]]:
    """(user_id, legacy_position, new_position) within each bracket, for users
    whose position the behaviour layer changes. Worst regressions first.
    """
    changes = []
    for members in brackets(candidates).values():
        new = _positions(rank(members))
        old = _positions(legacy_rank(members))
        changes += [
            (uid, old[uid], new[uid]) for uid in old if old[uid] != new[uid]
        ]
    return sorted(changes, key=lambda m: m[2] - m[1], reverse=True)


def _positions(ranked: Sequence[Candidate]) -> dict[str, int]:
    return {c.user_id: i for i, c in enumerate(ranked)}
