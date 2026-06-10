from __future__ import annotations

from analysis.shadow import brackets, legacy_rank, rank_changes
from newton.models import Candidate


def test_legacy_ignores_behaviour_score():
    a = Candidate("a", 0, 0, 10)
    b = Candidate("b", 0, 0, 200)
    assert [c.user_id for c in legacy_rank([a, b])] == ["a", "b"]


def test_brackets_group_by_admin_priority():
    pool = [
        Candidate("a", 0, 0, 1),
        Candidate("b", 0, 0, 2),
        Candidate("c", 0, 1, 3),
    ]
    sizes = {key: len(members) for key, members in brackets(pool).items()}
    assert sizes == {(0, 0): 2, (0, 1): 1}


def test_rank_changes_within_a_bracket():
    low = Candidate("low", 0, 0, 10)
    high = Candidate("high", 0, 0, 200)
    moved = {uid: (old, new) for uid, old, new in rank_changes([low, high])}
    assert moved["high"] == (1, 0)
    assert moved["low"] == (0, 1)


def test_behaviour_cannot_reorder_across_distinct_priorities():
    a = Candidate("a", 0, 0, 10)
    b = Candidate("b", 0, 1, 200)  # different bracket — priority dominates
    assert rank_changes([a, b]) == []
