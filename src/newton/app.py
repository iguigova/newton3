"""A runnable HTTP shell around the read API — standard library only.

`python -m newton.app` starts a server seeded with the demo users, so the API
the docs describe is something you can actually call:

    curl -s localhost:8000/users/bob/behavior-score
    curl -s 'localhost:8000/allocation?capacity=1'

This is the only place that opens a socket; in production the same
`api.behavior_score` / `api.allocation_report` functions are a Lambda handler
instead. Kept dependency-free on purpose — the project runs on the standard
library alone, so a clone can curl this with nothing installed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from newton.allocate import to_candidate
from newton.api import allocation_report, behavior_score
from newton.config import Config
from newton.models import Event, EventType
from newton.store import EventStore, InMemoryStore

# Override on so carol (3 offences) trips the restriction in /allocation.
CONFIG = Config(offence_override=2)
DEMO_USERS = ("alice", "bob", "carol")


def seed(now: datetime) -> InMemoryStore:
    """The CLI demo's three users, dated relative to `now` so scores are
    stable whenever the server starts (bob is always ~102).
    """
    day = timedelta(days=1)
    store = InMemoryStore()
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
    return store


def route(
    path: str,
    query: dict[str, list[str]],
    store: EventStore,
    config: Config,
    *,
    now: datetime,
) -> tuple[int, Any]:
    """Map (path, query) to (status, JSON-able body). Pure — the HTTP shell
    only serialises what this returns, so routing is testable without a socket.
    """
    parts = path.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "users" and parts[2] == "behavior-score":
        return 200, behavior_score(store, config, parts[1], now=now)
    if parts == ["allocation"]:
        capacity = _int(query.get("capacity", ["1"])[0], default=1)
        candidates = [
            to_candidate(u, store.events(u), config, now=now)
            for u in DEMO_USERS
        ]
        return 200, allocation_report(candidates, capacity=capacity)
    return 404, {
        "error": "not found",
        "routes": [
            "/users/{id}/behavior-score",
            "/allocation?capacity=1",
        ],
    }


def _int(value: str, *, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


class _Handler(BaseHTTPRequestHandler):
    store: EventStore = InMemoryStore()
    config: Config = CONFIG

    def do_GET(self) -> None:  # noqa: N802 (stdlib-mandated name)
        url = urlparse(self.path)
        status, payload = route(
            url.path,
            parse_qs(url.query),
            self.store,
            self.config,
            now=datetime.now(timezone.utc),
        )
        body = json.dumps(payload, indent=2, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(prog="newton.app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    _Handler.store = seed(datetime.now(timezone.utc))
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"newton read API on http://{args.host}:{args.port}")
    print("  GET /users/{id}/behavior-score   (try bob, alice, carol)")
    print("  GET /allocation?capacity=1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
