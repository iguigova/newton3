from __future__ import annotations

import pytest

from newton.allocate import decide, gsi_sort_key, rank
from newton.models import Candidate


def test_rank_orders_by_group_then_user_then_score():
    a = Candidate("a", 0, 0, 90)
    b = Candidate("b", 0, 0, 110)
    c = Candidate("c", 1, 0, 200)  # worse group priority sinks despite score
    assert [x.user_id for x in rank([a, b, c])] == ["b", "a", "c"]


def test_gsi_key_sorts_best_score_first():
    high = Candidate("high", 0, 0, 150)
    low = Candidate("low", 0, 0, 50)
    assert gsi_sort_key(high) < gsi_sort_key(low)


def test_gsi_key_order_matches_rank_across_all_layers():
    # the packed DynamoDB key must reproduce rank()'s full 4-layer order.
    cands = [
        Candidate("a", 0, 0, 100),
        Candidate("b", 0, 1, 200),  # worse user_priority
        Candidate("c", 1, 0, 50),  # worse group_priority
        Candidate("d", 0, 0, 90),  # same bracket as a, lower score
        Candidate("e", 0, 0, 100, force_last=True),  # forced last
    ]
    by_rank = [c.user_id for c in rank(cands)]
    by_gsi = [c.user_id for c in sorted(cands, key=gsi_sort_key)]
    assert by_gsi == by_rank


def test_gsi_key_rejects_out_of_range_fields():
    with pytest.raises(ValueError, match="out of range"):
        gsi_sort_key(Candidate("neg", -1, 0, 100))
    with pytest.raises(ValueError, match="out of range"):
        gsi_sort_key(Candidate("big", 0, 0, 10_000))


def test_force_last_user_sorts_last_despite_score():
    good = Candidate("good", 0, 0, 50)
    flagged = Candidate("flagged", 0, 0, 200, force_last=True)
    assert [c.user_id for c in rank([flagged, good])] == ["good", "flagged"]
    assert gsi_sort_key(good) < gsi_sort_key(flagged)


def test_decide_allocates_top_capacity_and_explains_behaviour():
    hi = Candidate("hi", 0, 0, 100)
    lo = Candidate("lo", 0, 0, 50)
    decisions = {d.user_id: d for d in decide([hi, lo], capacity=1)}
    assert decisions["hi"].allocated
    assert decisions["hi"].reason == "allocated"
    assert not decisions["lo"].allocated
    assert "behaviour score" in decisions["lo"].reason


def test_decide_explains_the_offence_override():
    ok = Candidate("ok", 0, 0, 50)
    flagged = Candidate("flagged", 0, 0, 200, force_last=True)
    decisions = {d.user_id: d for d in decide([ok, flagged], capacity=1)}
    assert not decisions["flagged"].allocated
    assert "offence override" in decisions["flagged"].reason


def test_decide_explains_higher_admin_priority():
    vip = Candidate("vip", 0, 0, 10)
    other = Candidate("other", 1, 0, 200)  # better score, worse priority
    decisions = {d.user_id: d for d in decide([vip, other], capacity=1)}
    assert decisions["vip"].allocated
    assert "higher admin priority" in decisions["other"].reason


def test_decide_explains_a_tie_break_loss():
    # equal bracket, equal score: the loser is told it was the tie-break, not
    # given a confusing "score X was allocated and you have X".
    a = Candidate("a", 0, 0, 100)
    b = Candidate("b", 0, 0, 100)
    losers = [d for d in decide([a, b], capacity=1) if not d.allocated]
    assert len(losers) == 1
    assert "tied on behaviour score" in losers[0].reason


def test_decide_with_zero_capacity_explains_no_spaces():
    (decision,) = decide([Candidate("a", 0, 0, 100)], capacity=0)
    assert not decision.allocated
    assert decision.reason == "no spaces were available"


def test_decide_with_capacity_exceeding_candidates_allocates_all():
    cands = [Candidate("a", 0, 0, 100), Candidate("b", 0, 0, 50)]
    decisions = decide(cands, capacity=5)
    assert all(d.allocated for d in decisions)
    assert all(d.reason == "allocated" for d in decisions)
