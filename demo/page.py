"""What the page asks of the engine, run in the browser by Pyodide, in
demo/worker.js, over the repo's own modules. Each function takes and
returns JSON, so the page's JavaScript only draws."""

from __future__ import annotations

import contextlib
import io
import json
import runpy
import sys
from datetime import datetime, timedelta, timezone

from newton import Config, Event, EventType, evaluate, is_force_last
from newton.app import CONFIG, DEMO_USERS, seed
from newton.config import DEFAULT_WEIGHTS, DEFAULT_WINDOWS


def policy() -> str:
    """The enabled events with their weights and windows, the API's policy,
    and the API's demo users' events as days before now."""
    now = datetime.now(timezone.utc)
    store = seed(now)
    return json.dumps(
        {
            "events": [
                {
                    "type": t.name,
                    "name": t.value,
                    "weight": w,
                    "window": DEFAULT_WINDOWS[t],
                }
                for t, w in DEFAULT_WEIGHTS.items()
            ],
            "config": {
                "base": CONFIG.base,
                "reward_cap": CONFIG.reward_cap,
                "floor": CONFIG.floor,
                "escalation": CONFIG.escalation,
                "offence_override": CONFIG.offence_override,
            },
            "users": {
                u: [
                    [e.type.name, round((now - e.at) / timedelta(days=1))]
                    for e in store.events(u)
                ]
                for u in DEMO_USERS
            },
        }
    )


def score(request: str) -> str:
    """Score one user's events, each given as [type, days before now]."""
    asked = json.loads(request)
    now = datetime.now(timezone.utc)
    config = Config(**asked["config"])
    events = [
        Event("you", EventType[t], now - timedelta(days=d), f"e{i}")
        for i, (t, d) in enumerate(asked["events"])
    ]
    result = evaluate(events, config, now=now)
    impacts = [
        {
            "name": i.type.value,
            "days": (now - i.at) / timedelta(days=1),
            "points": i.points,
        }
        for i in result.impacts
    ]
    return json.dumps(
        {
            "score": result.score,
            "tier": result.tier.value,
            "base": config.base,
            "floor": config.floor,
            "cap_adjustment": result.reward_cap_adjustment,
            "raw": config.base
            + sum(i["points"] for i in impacts)
            + result.reward_cap_adjustment,
            "impacts": impacts,
            "force_last": is_force_last(events, config, now=now),
        }
    )


def run(argv: str) -> str:
    """Run `python -m <module> <args>` and return what it printed."""
    module, *args = json.loads(argv)
    out = io.StringIO()
    sys.argv = [module, *args]
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            if module == "pytest":
                import pytest

                pytest.main(args)
            else:
                runpy.run_module(module, run_name="__main__", alter_sys=True)
        except SystemExit:
            pass
    return json.dumps(out.getvalue())
