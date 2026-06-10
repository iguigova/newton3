# Newton 3 — Demo

A five-minute demo in four beats, one story: the score is a transparent fold; edge cases
hold; it targets abuse, not the underserved; and behaviour acts where the legacy system
was random.

## ▶ Start here — the live demo

**▶ [Open the live demo](https://iguigova.github.io/newton3/deliverables/demo.html) — the
actual engine running in your browser.** This is the one to open first: a single scrollable
page with a faithful port of [`newton/engine.py`](../src/newton/engine.py) that recomputes
the score and its reconciling trace live as you add events and drag them through time. No
install, nothing to run. It also carries verbatim API request/response, the mandatory
proposals (#1, #8), the 1,200-user impact audit, and the ML stretch — the whole project in
one self-contained file. (Source: [`demo.html`](demo.html).)

## Two decks

Both are self-contained HTML — open the live link, `←`/`→` to move, `F` for fullscreen.
Screen-record either one for a video.

| Deck | Live link | What it shows |
|---|---|---|
| **Live demo** ⭐ | [demo.html](https://iguigova.github.io/newton3/deliverables/demo.html) | The engine running in the browser — interactive event builder + live reconciling trace, plus API I/O, proposals, impact, and ML, in one page. |
| **Pitch** | [slides.html](https://iguigova.github.io/newton3/deliverables/slides.html) | The problem, the reframing, proposals #1 and #8, data impact, and how it runs without AWS. |
| **Walkthrough** | [walkthrough.html](https://iguigova.github.io/newton3/deliverables/walkthrough.html) | Five screens of real command output — the suite, the score, the edge cases, the 1,200-user audit, the ML stretch — each with commentary. |

Every figure and code block in these pages is real program output captured from the four
commands below.

## The commands

Run from the repository root:

```bash
python -m pytest -q          # 63 tests pass — the engine is the thing under test
python -m newton.cli demo    # transparent score + explained allocation
python -m newton.app         # serve the read API on :8000 — curl it live (stdlib only)
python -m analysis.scenarios # decay, per-event fairness, cap, floor, clock skew
python -m analysis.impact    # data audit -> analysis/REPORT.md
python -m analysis.predict   # ML stretch: predictive no-show -> overbooking factor
```

## The beats

**1. The engine is the thing under test.** The brain is a pure function of
`(events, config, now)`, so the suite is plain input → output — 63 cases, no mocks,
including edge cases and data invariants.

**2. The score is transparent.** `cli demo` ranks three users, restricts the repeat
offender (proposal #1), and allocates one space with a reason for every outcome — a
behaviour cutoff for one, a restriction for the offender (proposal #8). The API response
carries `recent_impacts`: the per-event trace that reconciles to the score — the GDPR
Article 22 surface, and the answer to "allocation feels random" and "nobody tells me why."

**3. Edge cases hold.** A single offence recovers linearly — the penalty shrinks 1.25 per
week (−5.00 → 0.00) and the integer score is that value rounded half-up. Rewards saturate
at +20, the score floors at 0, and a future-dated event counts at full weight, never more.

**4. It targets abuse, not the underserved.** On 1,200 synthetic users under a long-memory
profile, the multi-misser tier M falls to a mean of 90 (16% Bronze-or-below) while the
high-demand underserved A, B, C stay near base — the same engine, by `Config` alone.
Under the documented defaults the score barely moves: a real finding, and the case for
tenant-configurable windows. The shadow comparator in `analysis/shadow.py` shows whom the
order reorders before any cut-over.

## Close

The score is one pure function. Persistence, per-event decay, explainability, and
per-tenant configuration are **properties of it, not subsystems** to build or keep in
sync — and the weekly decay job is gone entirely. Two design questions (Platinum
reachability, score-reset semantics) and one scaling tradeoff are **owned explicitly**
in [`docs/README.md`](../docs/README.md#open-questions) for the author to settle — flagged,
not hidden.

## Notes

- Nothing in either deck or any command prints user PII; all output is aggregate or
  synthetic.
