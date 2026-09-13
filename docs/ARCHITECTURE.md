# ARCHITECTURE.md

## The shape of the system

```
Discord /log  ──►  Judge (Qwen3-VL on Bedrock + POLICY.md)  ──►  Verdict (typed)
                                                        │
                                                        ▼
                                                    Ledger (append-only)
                                                        │
                                        weekly trigger  ▼
                                                   Leaderboard
                                                        │
                                                        ▼
                                              Planner (consequence plan)
                                                        │
                                                        ▼
                                    ┌───────────────────┼───────────────────┐
                                    ▼                   ▼                   ▼
                              Google Calendar     Google Sheets         Spotify
                             (find slot, invite)   (debt ledger)     (shame playlist)
                                    └───────────────────┼───────────────────┘
                                                        ▼
                                                 Discord announcement
                                                    + role assignment
```

## Two-pass judging

The judge is not one model call. It is:

```
Pass 1  EXTRACT   image only, claim withheld   → ObservedMetrics
Pass 2  COMPARE   deterministic code            → verdict + reason code
Pass 3  DISAMBIGUATE (only if needed)           → activity-type plausibility
```

Pass 1 never sees what the member claimed, so it cannot anchor on it. Pass 2 is
arithmetic against `POLICY.md`. Pass 3 calls the model again only for the genuinely
fuzzy question, and only when pass 2 is inconclusive.

Full rationale and the other seven hallucination failure modes are in
`docs/MODEL_RELIABILITY.md`. Read it before writing `agent/judge.py`.

## The one design decision that matters

**The model produces typed output. Deterministic code takes the actions.**

The judge returns a `Verdict`. The planner returns a `ConsequencePlan`. Neither
calls an API. `enforcer/actions/` reads the plan and executes it with idempotency
keys and logging.

This is what separates a reliable agent from a prompt with API access, and it's
what you point at when a judge asks how you keep it from going off the rails. It
also means every model output is testable in isolation, which is what makes the
eval harness possible at all.

## Schemas

Use pydantic. Every model call validates into one of these or retries once.

```python
class Submission(BaseModel):
    id: str
    member_id: str
    submitted_at: datetime          # via core.clock
    claimed_activity: ActivityType
    claimed_duration_min: int | None
    claimed_distance_km: float | None
    image_ref: str                  # local path or Discord CDN URL
    note: str | None

class Verdict(BaseModel):
    submission_id: str
    verdict: Literal["ACCEPT", "REJECT", "ESCALATE"]
    reason_code: ReasonCode | None  # required when REJECT
    points: int                     # 0 unless ACCEPT
    confidence: float               # 0.0–1.0
    rationale: str                  # one or two sentences, shown to the member
    observed: ObservedMetrics       # what the model actually read off the image
    policy_version: str

class ObservedMetrics(BaseModel):
    activity_seen: str | None
    duration_min: float | None
    duration_source: str | None      # literal on-screen text it was read from
    distance_km: float | None
    distance_source: str | None
    date_seen: date | None
    date_source: str | None
    evidence_kind: Literal["tracker_screenshot", "photo", "watch_face",
                           "unclear"]

# A non-null metric with no source span is rejected in code.
# A non-null metric with evidence_kind == "unclear" forces ESCALATE.
# See MODEL_RELIABILITY.md §1.

class ConsequencePlan(BaseModel):
    loser_id: str
    week_start: date
    proposed_slots: list[TimeSlot]  # from freebusy, planner ranks them
    chosen_slot: TimeSlot
    venue_hint: str | None
    debt_amount: float
    playlist_theme: str
    actions: list[PlannedAction]
```

`observed` is doing real work. Storing what the model *saw* separately from what it
*decided* is what lets you debug a bad verdict, and it makes the rationale
trustworthy to the member reading it.

## The action layer

Every external write goes through here. No exceptions, no direct API calls from
the bot or the agent.

```python
# enforcer/actions/base.py
class Action(Protocol):
    kind: str
    idempotency_key: str
    def execute(self, ctx: Context) -> ActionResult: ...
    def describe(self) -> str: ...   # for dry-run and the audit log
```

Rules:

- **Idempotency key** is deterministic from content, e.g.
  `f"cal:{week_start}:{loser_id}"`. Re-running the week must not create a second
  calendar event, a second expense, or a second playlist. Demos get re-run. This
  will save you.
- **Every execution appends one JSONL line** to `run_log.jsonl`: timestamp, kind,
  key, dry_run flag, result, latency, error. This file is your audit trail, your
  debugging tool, and a slide in your brief.
- **Dry-run** short-circuits `execute()` and logs `describe()` instead. The full
  flow must run with `ENFORCER_DRY_RUN=true` and touch nothing external.
- **Retries:** two attempts with backoff on 5xx and timeouts. Never retry a 4xx.
  Log the failure and continue; one dead integration must not abort the chain.

## Integrations

Each one is an interface with two implementations.

```
integrations/calendar/   base.py  google.py  fake.py
integrations/sheets/     base.py  live.py    fake.py
integrations/spotify/    base.py  live.py    fake.py
integrations/discord/    base.py  live.py    fake.py
```

Write `fake.py` first, always. It unblocks the whole downstream pipeline while the
real auth is still being fought, and it's what the eval harness runs against.

Selected by env var: `ENFORCER_INTEGRATIONS=fake|live|mixed`. Mixed reads a
per-integration override so you can run Calendar live and everything else fake
while you're debugging.

## The clock

```python
# enforcer/core/clock.py
class Clock(Protocol):
    def now(self) -> datetime: ...

class RealClock: ...
class SimulatedClock:          # advance(days=1) for the seeded week
    def advance(self, **kw): ...
```

Nothing else in the codebase may call `datetime.now()`. This single abstraction
gives you the demo (fast-forward a week in 20 seconds) and half the eval harness
(replay a week deterministically). It costs 15 lines. Build it in the first hour.

## The ledger

Append-only JSONL: one line per verdict. Never mutate, never delete. The
leaderboard is a pure function of the ledger plus the policy.

```python
def leaderboard(ledger: list[Verdict], week: DateRange) -> list[Standing]
```

Pure function means it's trivially testable and it can't drift out of sync with the
underlying data. Recompute it every time rather than maintaining running totals.

## The judge prompt

Lives in `enforcer/llm/prompts/judge.md`. Structure:

1. The full text of `POLICY.md`
2. The output schema, with an explicit instruction to return JSON only
3. Three or four worked examples, including **one ACCEPT, one REJECT with a reason
   code, and one ESCALATE** — the escalate example matters most, because without it
   models almost never escalate
4. The submission: image + claimed metadata + the member's recent submission
   history (for `R1_DUPLICATE` detection)

Duplicate detection is partly deterministic: hash the image and check the last 14
days before you even call the model. Cheap, exact, and it removes an entire failure
mode from the model's plate. Do the same for `R2_STALE` where EXIF is available.

**General principle: anything you can decide with code, decide with code.** Give the
model only the judgments that genuinely need judgment. This is the same instinct as
the deterministic matching layer in KaaryaSetu, and it's the right one here too.

## Consequence chain ordering

Execute in this order, and continue on failure:

1. **Discord announcement + role assignment** — cheapest, always works, and it means
   the demo has a visible result even if everything downstream fails
2. **Calendar** — freebusy across members, pick the slot, insert the event with
   `sendUpdates="all"`
3. **Google Sheets** — append the debt row to the ledger, and render the UPI
   payment QR into the Discord embed
4. **Spotify** — create the playlist, add tracks

Then post a final Discord embed summarising what succeeded and what failed. A
system that says "3 of 4 actions completed, Spotify timed out" is more impressive
than one that pretends everything is fine.

**Compensating actions** (define them even though we use forward recovery):
`delete_event`, `mark_debt_row_void`, `unfollow_playlist`.

**Sheets has no native idempotency.** `values.append` will happily write the same
row twice. Before appending, read column A (the idempotency keys) and skip if the
key is already present. This read-then-append is not atomic, but with one writer
and a weekly cadence that is fine — note the limitation in the brief rather than
pretending otherwise.

## Configuration

All config in `.env`, loaded once into a typed `Settings` object. No scattered
`os.getenv` calls. See `.env.example`.
