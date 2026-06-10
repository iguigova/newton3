from __future__ import annotations

from datetime import datetime, timezone

from newton.app import CONFIG, route, seed

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_behavior_score_route_returns_the_api_payload():
    store = seed(NOW)
    status, body = route(
        "/users/bob/behavior-score", {}, store, CONFIG, now=NOW
    )
    assert status == 200
    assert body["user_id"] == "bob"
    assert body["score"] == 102
    assert body["recent_impacts"]  # the GDPR trace is present


def test_allocation_route_respects_capacity_and_explains():
    store = seed(NOW)
    status, body = route(
        "/allocation", {"capacity": ["1"]}, store, CONFIG, now=NOW
    )
    assert status == 200
    allocated = [r for r in body if r["allocated"]]
    assert len(allocated) == 1  # one space
    assert all("reason" in r for r in body)


def test_unknown_path_is_404_with_route_hints():
    status, body = route("/nope", {}, seed(NOW), CONFIG, now=NOW)
    assert status == 404
    assert "routes" in body


def test_bad_capacity_falls_back_to_default():
    status, body = route(
        "/allocation", {"capacity": ["abc"]}, seed(NOW), CONFIG, now=NOW
    )
    assert status == 200
    assert sum(r["allocated"] for r in body) == 1
