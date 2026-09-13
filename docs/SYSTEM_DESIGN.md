# SYSTEM_DESIGN.md — Concepts, Seams, and the Scaling Path

This document exists so that the six-hour build doesn't become a thing you have to
throw away. It has two jobs:

1. Name the system design concepts that genuinely apply to The Enforcer, and say
   what each one looks like at hackathon scale versus real scale.
2. Identify the **seams** — the decisions that cost nothing on Sunday but make the
   difference between "extend it" and "rewrite it" later.

It also doubles as interview prep. Top three teams get interviews, and "why did you
build it that way" is the question you'll get. The answers are in here.

---

## The governing principle: seams, not scaffolding

The failure mode for a hackathon project that wants to scale later is building the
scaled version. Queues, workers, service boundaries, and a Postgres schema on day
one will cost you the hackathon and you'll have guessed wrong about the load
anyway.

The opposite failure is a tangle where the fix requires touching every file.

The middle path is **seams**. A seam is a place where you could later cut the system
apart without rewriting either side. Seams are almost free when you put them in
first and expensive to retrofit.

The test for whether something is worth doing now:

> **Does this cost me less than 20 minutes today, and would adding it later mean
> touching more than three files?**

If yes, do it now. If no, write it down here and move on.

---

## Part 1 — The seams worth taking on Sunday

Every one of these is a one-line or one-parameter decision. Together they're maybe
40 minutes of work and they carry the entire scaling story.

| Seam | What you do Sunday | Why it matters later |
|---|---|---|
| **Tenant key on every record** | Put `guild_id` in every ledger entry, verdict, and action, even though there is exactly one server | Multi-tenancy is a partition key problem. Adding it later means backfilling every table and auditing every query for tenant leakage. Adding it now is one field. |
| **Append-only ledger** | JSONL, never mutate a row | This makes the ledger an event log. Everything in Part 2A follows from it. |
| **Leaderboard as a pure function** | `leaderboard(events, week) -> standings`, recomputed each time | A pure fold over an event log becomes an incremental projection with a checkpoint. A stateful running total becomes a bug. |
| **Content-addressed images** | Key images by SHA-256 of the bytes | Free deduplication, free verdict caching, and a clean move to object storage. |
| **`policy_version` on every verdict** | One string field | Without it you can never tell whether an old verdict is comparable to a new one, and your eval baselines silently rot. |
| **Idempotency key on every effect** | Deterministic from content: `cal:{week}:{loser}` | Turns "at least once" delivery into "effectively once" outcomes. Retrofitting this after a double-booking incident is miserable. |
| **Correlation ID per submission** | One UUID threaded through logs, model calls, and actions | This is the difference between debugging by grep and debugging by trace. |
| **Ports and adapters** | Interface + `live.py` + `fake.py` per integration | Already in `ARCHITECTURE.md`. It's what makes the eval harness and the offline demo possible, and later it's what makes a service extraction mechanical. |
| **Clock as a dependency** | `core/clock.py`, nothing else calls `now()` | Testability, replay, and later, correctness under distributed scheduling. |
| **Repository interface for storage** | `LedgerRepo` protocol with a JSONL implementation | JSONL → SQLite → Postgres becomes one new class, not a refactor. |

That's the whole list. Everything below this line is context for *why*, plus what
you'd actually build if this got real.

---

## Part 2 — Concepts, applied

### A. State and data

**Event sourcing.** The ledger is an event log, not a table of current state. A
verdict is an immutable fact: at time T, submission S was judged V under policy
version P. Current standings are derived, never stored as truth.

This is the right model here for a reason beyond elegance: the system makes
contested judgments about people, and people appeal. An append-only log means an
appeal adds a *new* event (`VerdictOverridden`) rather than editing history. You
keep the full record of what was decided and why, which is exactly what you want
when someone disputes losing.

- **Sunday:** JSONL file, one event per line.
- **At scale:** Postgres table with `(tenant_id, stream_id, seq)`, or a real log if
  volume demands it. The application code doesn't change.
- **Seam:** never mutate, never delete.

**CQRS and read models.** Writes go to the log; reads come from projections. The
leaderboard is a projection. So is a member's submission history, and so is the
appeals queue.

- **Sunday:** recompute the projection on every read. At five members and forty
  events it's microseconds.
- **At scale:** incremental projection with a stored checkpoint (`last_seq`), rebuilt
  from scratch on demand. Rebuildability is the property that matters — if a
  projection can always be reconstructed from the log, a projection bug is an
  inconvenience rather than data loss.
- **Seam:** pure function signature.

**Storage evolution.** JSONL → SQLite → Postgres. The interesting question isn't
which database, it's what the access patterns are: append-heavy writes, range reads
by `(tenant, week)`, and occasional full scans for rebuilds. That's a boring
workload, which is good.

**Blob storage.** Submission images are the only large objects.

- **Sunday:** Discord's CDN URL plus a local copy for the eval set.
- **At scale:** content-addressed object storage (S3/MinIO), key = image hash.
  Because the key is the hash, storing the same image twice is a no-op, and the
  duplicate check becomes a key lookup instead of a scan.
- **Privacy note:** these are photos of people. See Part 2G.

### B. Making effects reliable

This is the section that matters most for the hackathon, and it's the part most
teams get wrong.

**The core problem:** the consequence chain touches four external systems and there
is no distributed transaction available. The calendar event can succeed and the
Sheets row can fail. You cannot make this atomic. You can make it
*recoverable*.

**Idempotency.** Every effect carries a deterministic key derived from its content.
Before executing, check whether that key has already succeeded. This converts retry
safety from "hope" into a property.

The subtlety: the key must derive from *what the action means*, not from when it
ran. `cal:2026-W37:sisanta` is right. `cal:{uuid4()}` is useless.

**The outbox pattern.** Write the intent, then execute it, then record the result.
The `ConsequencePlan` is an outbox: a durable list of intended actions, each
independently executable and independently retryable.

- **Sunday:** the plan is a JSON blob and a for-loop with logging.
- **At scale:** an `outbox` table, a worker polling for unexecuted rows, at-least-once
  delivery made safe by the idempotency keys. Same shape, different substrate.

**Sagas and compensation.** When step 3 of 4 fails permanently, you have two
choices:

- **Forward recovery:** complete what you can, report what you couldn't. Correct for
  this system — a party that's booked but not yet split is fine, someone will sort
  it out.
- **Backward compensation:** undo the earlier steps. Needed when partial completion
  is worse than nothing.

The Enforcer uses forward recovery, and that's a deliberate choice you should be
able to defend. But define the compensating action for each step anyway
(`delete_event`, `delete_expense`, `unfollow_playlist`), because it costs a few
lines and it's the answer to "what if you booked the wrong week?"

**Ordering matters.** The chain runs cheapest-and-most-reliable first: Discord
announcement, then Calendar, then Sheets, then Spotify. If everything downstream
fails, the demo still shows a visible outcome. Order your side effects by the
blast radius of their failure.

**Circuit breakers and bulkheads.** One misbehaving integration must not consume the
whole system. A per-integration circuit breaker (open after N consecutive failures,
half-open after a cooldown) means a Spotify outage degrades one feature instead of
stalling every consequence chain behind a 30-second timeout.

- **Sunday:** a timeout and a try/except that logs and continues. That *is* the
  bulkhead, in its simplest form.
- **At scale:** real breakers, separate connection pools, separate worker pools per
  integration.

**Timeouts, retries, backoff.** Every network call gets an explicit timeout — there
is no such thing as a reasonable default. Retry only on 5xx and timeouts, never on
4xx. Exponential backoff with jitter, because synchronized retries are how a
recovering service gets knocked over again.

Add a **retry budget**: cap total retries per task, so a failing dependency can't
turn one submission into forty API calls.

### C. Concurrency and load

**Where the load actually is.** Judging is the expensive step: a vision model call
per submission, order of seconds. Everything else is milliseconds. This is a
classic asymmetric workload, and it tells you exactly where the queue goes.

**Queue-based load leveling.** The Discord interaction has a 3-second
acknowledgement window; a vision call doesn't fit. So the pattern is forced on you
and it happens to be the right one: acknowledge immediately, enqueue, process
asynchronously, follow up.

- **Sunday:** `asyncio.Queue` and a worker task, with a `Semaphore` bounding
  concurrent model calls. Defer the Discord response, edit it when the verdict lands.
- **At scale:** RabbitMQ or similar between the bot and a judge worker pool, with
  KEDA scaling workers on queue depth. The bot becomes a thin ingress that does
  nothing but validate and enqueue.
- **Seam:** the moment `judge()` is called from a worker rather than inline, the
  queue substrate is swappable. Get that shape right on Sunday even with an
  in-process queue.

**Backpressure.** A bounded queue that rejects when full is better than an unbounded
one that dies. At hackathon scale you'll never hit it; setting `maxsize` anyway
costs one argument and makes the behaviour explicit.

**Rate limiting.** Two directions:

- *Outbound:* token bucket per provider. Discord in particular has both a global
  limit and per-route buckets, and it returns `X-RateLimit-*` headers you should
  actually respect. discord.py handles most of this; your own httpx calls don't.
- *Inbound:* per-member submission limits. Not a scaling concern — an abuse concern.
  Someone will spam `/log` twenty times to find a photo that passes.

**Idempotent scheduling.** Weekly settlement is a scheduled job. With one process
this is a timer. With N replicas, all N fire, and you book four parties.

- **Sunday:** a single timer in a single process.
- **At scale:** leases. A worker claims `settle:{tenant}:{week}` with a
  compare-and-set before running. The idempotency key on the effects is your second
  line of defence if the lease logic is ever wrong.

### D. The model layer

**Functional core, imperative shell.** The deterministic parts are pure and testable;
the model calls and the API calls live at the edges. This is why the model returns
a `Verdict` rather than calling a tool. It's the single most important structural
decision in the system.

Practical consequence: you can run your entire eval suite without a Discord server,
a Google account, or a network connection to anything but the model provider. And
later, you can swap the model without touching the business logic.

**Push work down the stack.** Duplicate detection is a hash lookup. Stale-date
detection is EXIF plus arithmetic. Threshold checks are comparisons. None of these
need a model. Reserve the model for the thing only a model can do: looking at a
photo and deciding whether it's consistent with a claim.

This is a reliability argument before it's a cost argument. Deterministic checks
have 100% accuracy and 0ms latency, and every judgment you move out of the model is
a judgment that can't be wrong stochastically.

**Cascading.** At volume, the natural evolution is a cheap first pass that handles
the obvious cases and escalates the ambiguous ones to the expensive model. Most
submissions are unambiguous. This is the same escalation logic you already have for
human review, applied one layer down.

**Serving.** Not a Sunday concern, but the honest answer if asked: at meaningful
volume you'd self-host a VL model behind vLLM with continuous batching, since the
workload is bursty (everyone logs in the evening) and batchable (no user is waiting
on a sub-second response — they've already got their deferred acknowledgement).
That bursty-but-latency-tolerant profile is close to ideal for batched inference.

**Caching.** Verdict cache keyed on `(image_hash, claimed_metadata, policy_version)`.
The policy version in the key is the part people forget: change the thresholds and
every cached verdict becomes wrong, silently.

**Determinism and variance.** Model output isn't deterministic. Temperature 0 helps
and doesn't solve it. Treat verdict stability as a measured property (see
`EVAL.md`, `--repeat`) rather than an assumption. A system that knows its own
flip rate is more trustworthy than one that assumes zero.

### E. Quality and feedback loops

**Evals as a regression gate.** The 40-case set is a test suite. At scale it runs in
CI and blocks a deploy on regression, exactly like unit tests, except the pass
threshold is a percentage rather than binary.

**Offline versus online evaluation.** The labeled set is offline. Online, you'd
sample a fraction of production verdicts for human review and track agreement.
Offline tells you if you broke something; online tells you if reality moved.

**Appeals are labeled data.** This is the nicest property of the design. Every
appeal is a human telling you the model was wrong, on a real case, for free. At
scale, overturned verdicts flow straight into the eval set, and the eval set grows
toward exactly the cases the system finds hard. Build the appeal flow and you've
built a data engine.

**Drift detection.** Track the verdict distribution over time. A sudden rise in
`R3_NOT_SUBMITTER` means either a new cheating technique or a broken prompt. Either
way you want to know within a day, not a month. Distribution shift is usually the
first observable symptom of both model degradation and adversarial adaptation.

**Human-in-the-loop as a first-class component.** Escalation isn't an error path,
it's a designed outcome with its own queue, its own latency target, and its own
interface. Systems that make judgments about people need a defined route to a human,
and designing it in from the start is much cheaper than bolting it on after the
first angry user.

### F. Operations

**Observability.** Structured JSON logs with the correlation ID on every line. The
three things worth measuring here:

- *Verdict latency* (p50/p95) — user-visible
- *Verdict distribution* — quality signal and drift signal
- *Action success rate by integration* — tells you which dependency is rotting

The `run_log.jsonl` is a primitive version of all three, and it's genuinely enough
for Sunday. It's also a slide in your brief.

**Configuration and policy as data.** `POLICY.md` is loaded at runtime, not compiled
in. That means changing the rules doesn't require a deploy, and different groups can
have different rules — which is the multi-tenancy story arriving through the front
door rather than as a retrofit.

**Schema versioning.** `policy_version` on verdicts, and a version on the event
schema itself. Old events must remain readable forever, because the whole value of
an append-only log is that you can replay it. Additive changes only; never
repurpose a field.

### G. Trust, safety, and abuse

Worth a section because this system has properties that most hackathon projects
don't: it processes **photos of people**, and it makes **adversarial** judgments.

**Adversarial users are the design assumption, not an edge case.** The people being
judged have a direct incentive to fool the judge, and unlike most ML systems, they
get immediate feedback on what works. Consequences:

- Rate-limit submissions per member per day, or `/log` becomes a brute-force oracle
- Log rejected attempts; the pattern of what people try is the roadmap for what to
  harden
- Assume any check you document publicly will be probed

**Data minimisation.** Submission images are personal data. At scale: a stated
retention window, deletion on request, encryption at rest, and access limited to
the group the submission was made in. Cross-tenant image access would be a serious
breach, which is another argument for the tenant key being present from line one.

**Scope discipline in the model.** The judge rules on whether an activity happened
and met a threshold. It must never comment on bodies, weight, appearance, or
fitness level. This is in `POLICY.md` as a hard rule. It's the right call ethically,
and it's also the difference between a demo that lands and one that makes a room
uncomfortable.

**Fairness of the mechanism.** The rules are written down, visible to everyone,
applied uniformly, and appealable. That's not decoration — it's what makes an
automated judge socially acceptable to the people it judges. Any system that
imposes consequences on people needs a legible rule set and a route to challenge it.

---

## Part 3 — What actually changes at each stage

### Stage 1: one server, five people (Sunday)

Single Python process. In-process asyncio queue. JSONL files. Local images. A timer
for weekly settlement.

**Bottleneck:** none. You will not find one.

### Stage 2: hundreds of servers, thousands of members

```
Discord ──► Bot (thin ingress, N replicas)
                    │ enqueue
                    ▼
              RabbitMQ ──► Judge workers (KEDA-scaled on queue depth)
                                  │
                                  ▼
                            Postgres (events + projections)
                                  │
                            Outbox worker ──► Calendar / Sheets / Spotify
                                  │
                            Scheduler (leased weekly settlement)
```

What changes:

- Files become Postgres, behind the same repository interface
- The asyncio queue becomes RabbitMQ, behind the same worker interface
- The for-loop over actions becomes an outbox table plus a worker
- The settlement timer grows a lease
- Images move to object storage, still keyed by hash
- Projections become incremental with checkpoints

What doesn't change: the judge, the policy loader, the leaderboard function, the
schemas, the integration adapters. That's most of the codebase, and it's the point
of the seams.

**Bottleneck:** model inference. Everything else is idle. This is why the queue goes
in front of the judge and nowhere else.

### Stage 3: serious volume

Self-hosted VL model behind vLLM with continuous batching. A cheap classifier
cascade in front of it so the expensive model only sees ambiguous cases. Regional
sharding by tenant if latency demands it. Read replicas for projections. Online
eval sampling feeding a continuously growing labeled set.

**Bottleneck:** cost per judgment, not throughput. The engineering question stops
being "can we serve this" and becomes "what fraction of submissions actually need
the big model."

---

## Part 4 — Explicitly not building now

Written down so that neither you nor Claude Code is tempted at 2pm on Sunday. Each
of these is a Stage 2 concern and adding it early costs you the hackathon.

- A database of any kind
- A real message broker
- Service boundaries, containers, or a deploy
- Auth beyond a bot token
- A web UI
- Multi-region anything
- A model cascade
- Distributed tracing infrastructure
- An admin dashboard

The seams in Part 1 are what make all of these cheap later. That's the whole trade:
**pay 40 minutes now for the seams, skip the several days of scaffolding, and
accept that the single-process version is the correct architecture for five
users** — which it genuinely is.

---

## The one-paragraph version, for when a judge asks

> It's an event-sourced system with a deterministic core and the model at the edge.
> The model only ever returns typed verdicts; deterministic code executes every
> effect, each with a content-derived idempotency key and an audit log entry, so
> re-running a week is safe. The consequence chain across four apps can't be
> atomic, so it's a saga with forward recovery and defined compensations, and it
> reports partial completion honestly rather than pretending. Every integration
> sits behind a port with a fake implementation, which is what makes the eval
> harness runnable offline. It's a single process today because five users don't
> justify anything more, but the tenant key, the append-only log, the pure
> projections and the queue shape are all in place, so the path to a worker pool
> behind a broker is a substrate swap rather than a rewrite.
