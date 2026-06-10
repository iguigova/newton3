# 🚀 Newton 3 — CLAUDE.md

## 📌 Context

You are helping to build **Newton 3.0**, a next-generation allocation engine for shared
workplace resources (parking, desks, EV chargers).

The goal is not incremental improvement — it's a reimagining of allocation that is:
- **Transparent** — decisions should be explainable
- **Fair** — behaviour-driven, not opaque rules
- **Scalable** — AWS-native, AI-ready architecture

This system:
- Replaces a legacy rule-based allocation service
- Is fully **AWS-native and serverless**
- Uses a **behaviour-driven scoring model**
- Must be implemented in **Python**

⚠️ Important:
You do NOT need to understand the legacy allocation service in depth.
Focus on building the **target system in Python**, using the specs below.
**No legacy dependency. No legacy coupling.**

---

## 🎯 Project Goals

Build a **working prototype** evaluated on:

1. **How well the solution works in practice**
2. **How many scenarios/functions it successfully handles**
3. **Simplicity and scalability of the approach**

Core deliverables:
1. Behaviour Scoring Engine
2. Allocation Engine (ranking users)
3. Event-driven architecture (simulated or real)

Stretch goals (the differentiators):
- AI-assisted scoring or anomaly detection
- Dynamic weight configuration per tenant
- Shadow mode comparator (new vs legacy output)
- Explainability layer ("why did Alice get a space?")
- Admin/CS visibility dashboard
- Gamification hooks

---

## 🧠 Core Concepts

### Behaviour Score

Each user starts with:

```
base_score = 100
```

Score is calculated as:

```
score = base_score + rewards - penalties + decay
```

#### Penalties
- Unused booking (no-show): `-3`
- Free space / non-paid usage: `-1`
- Offence (parking violation): `-5`

#### Rewards
- Carpool participation: `+5`

#### Decay (Recovery)
- `+2` per week since last penalty
- Cannot exceed base score (100)
- Formula: `decay = min(weeks_since_last_penalty * 2, base_score - current_score)`

#### Constraints
- Minimum score = `0`
- Reward cap = `+20` (rolling 4-week window)
- Score resets/reruns after each major allocation cycle

#### User Tiers
| Tier       | Score Range | Meaning           |
|------------|-------------|-------------------|
| Platinum   | 150+        | Excellent behavior|
| Gold       | 120–149     | Very good         |
| Silver     | 80–119      | Normal            |
| Bronze     | 50–79       | Needs improvement |
| Restricted | <50         | Poor behavior     |

---

### Allocation Logic

Priority is applied in layers:

```python
def allocation_sort(user):
    return (
        user.group_priority,    # Layer 1: Admin-controlled group
        user.user_priority,     # Layer 2: Admin override
        -user.behavior_score,   # Layer 3: Behaviour (higher = better)
        random()                # Layer 4: Tie-breaker
    )
```

---

## ⚙️ Architecture Guidelines

Target architecture:
- **Python**
- **AWS Lambda** (or equivalent functions — simulate locally if needed)
- **Event-driven** (simulate with in-memory queues if needed)
- **Modular design**

Suggested components:

```
scoring_engine.py     — score calculation, cap logic, decay
allocation_engine.py  — user ranking, allocation run
event_processor.py    — event ingestion, routing to scoring
models.py             — User, Event, Score data models
api.py                — REST endpoint (optional)
cli.py                — CLI simulator (optional)
tests/                — unit + scenario tests
```

Data layer:
- Use **in-memory dict / SQLite** for local prototype
- Design as if DynamoDB is the target (PK=`USER#{id}`, SK=`GROUP#{id}`)

---

## 🔁 Event-Driven Model

The system reacts to these events:

| Event                  | Source          | Score Impact   |
|------------------------|-----------------|----------------|
| `booking.created`      | Booking service | None           |
| `booking.cancelled`    | Booking         | None (or +5 if early cancel — TBD) |
| `booking.completed`    | Booking         | None           |
| `gate.entry_detected`  | Gate            | Validates show |
| `offence.reported`     | Reports         | -5             |
| `carpool.detected`     | Booking         | +5             |
| `unused_booking`       | Booking         | -3             |
| `free_space_used`      | Booking         | -1             |
| `weekly_decay`         | Scheduler       | +2 (capped)    |

```python
def process_event(event):
    score = get_score(event.user_id)

    if event.type == "unused_booking":
        score -= 3
    elif event.type == "free_space_used":
        score -= 1
    elif event.type == "offence":
        score -= 5
    elif event.type == "carpool":
        score += min(5, reward_headroom(event.user_id))  # cap-aware

    score = max(score, 0)
    save_score(event.user_id, score)
    log_event(event)
```

---

## 🗄️ Data Model (Simplified)

### User Score

```json
{
  "user_id": "123",
  "group_id": "engineering",
  "score": 104,
  "tier": "Gold",
  "last_penalty_at": "timestamp",
  "reward_total_rolling": 10,
  "updated_at": "timestamp"
}
```

### Events

```json
{
  "user_id": "123",
  "event_type": "carpool",
  "points": 5,
  "timestamp": "..."
}
```

---

## 🧪 MVP Scope

### Must have
- [ ] Event processing → score updates
- [ ] Score stored in memory / simple DB
- [ ] Decay calculation (weekly)
- [ ] Reward cap enforcement (rolling 4 weeks)
- [ ] Allocation function returning ranked users
- [ ] Simple test dataset with realistic scenarios

### Nice to have (stand out)
- [ ] REST API endpoint (`GET /users/{id}/behavior-score`)
- [ ] CLI to simulate event streams
- [ ] Explainability: "why did this user rank here?"
- [ ] Shadow mode: compare new vs mock-legacy output
- [ ] Tier display + history
- [ ] Logging / observability hooks

### Innovative / AI-driven (stretch / differentiators)
- [ ] LLM-assisted explanation of allocation decisions
- [ ] ML anomaly detection on scoring patterns
- [ ] Dynamic scoring weights per tenant config
- [ ] Predictive allocation (who is likely to no-show?)

---

## 🤖 How to Use Claude

You should:
- Generate Python code for each module
- Suggest improvements, refactors, and AI enhancements
- Help simulate AWS components locally
- Optimize for readability and modularity
- Write tests and scenario simulations
- Propose ideas that push beyond the spec (AI layer, explainability, etc.)

You should NOT:
- Depend on legacy code
- Overcomplicate with unnecessary infra
- Block progress due to missing legacy context
- Implement AWS infra directly — simulate locally first

---

## 🏗️ Suggested Workflow

1. Define models (`User`, `Event`, `Score`)
2. Implement scoring engine (penalties, rewards, cap, decay)
3. Implement event processor
4. Implement allocation logic
5. Simulate a realistic event stream
6. Validate ranking output against expected scenarios
7. Add explainability or AI layer (bonus)
8. Polish CLI / API for demo

---

## 🏆 Success Criteria

- Working Python implementation
- Clear separation of concerns
- Correct event-driven scoring logic
- Allocation produces correct, explainable ranking
- Handles edge cases (min score, reward cap, decay)
- Code is clean, testable, and extensible
- Bonus: something that surprises and delights

---

## 🔥 Mindset

- AI-first development (Claude)
- Speed over perfection — working > perfect
- Challenge assumptions — don't just implement the spec, improve it
- Focus on the **target system**, not the legacy
- Build something that could actually go to production

---

Let's build Newton 3. 🚀
