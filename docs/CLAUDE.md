# CLAUDE.md — The Enforcer

Read this first, every session. Then read `docs/ARCHITECTURE.md` before writing code.

`docs/MODEL_RELIABILITY.md` is required reading before writing the judge or any
prompt. `docs/SECURITY.md` is required before handling a user-submitted image or
posting model output publicly.

`docs/SYSTEM_DESIGN.md` explains *why* the architecture is shaped the way it is, and
lists the ten cheap "seams" that must be present in the Sunday build (tenant key,
append-only ledger, pure projections, content-addressed images, policy version,
idempotency keys, correlation IDs, ports and adapters, injected clock, repository
interface). Read Part 1 of it before starting; skim the rest when a design question
comes up. Part 4 lists what we are deliberately NOT building.

## What we are building

A group fitness accountability agent for the Multi-App AI Agent Hackathon
(virtual, Sunday 13 September 2026, 9:30am–4:00pm Pacific).

Members of a Discord server log workouts with photo proof. The agent judges each
submission against a written policy, maintains a weekly leaderboard, and then
**executes the consequence**: last place owes the group a party. The agent finds a
time everyone is free, creates the calendar event and sends invites, records the
debt as a group expense, and builds the loser a shame playlist.

The point is not the leaderboard. The point is that a system makes a **judgment
call** on ambiguous evidence and then **takes real action in real apps**.

## Hackathon constraints that drive every decision

| Criterion | Weight | What earns it here |
|---|---|---|
| Technical execution | 30% | Clean tool layer, typed verdicts, idempotent writes, real orchestration |
| Reliability & evaluation | 25% | Labeled eval set + precision/recall numbers + failure taxonomy |
| Usefulness | 20% | Real accountability loop people would actually run |
| Originality | 15% | Agent executes consequences, not just reports them |
| Demo clarity | 10% | 2-minute recorded demo, real artifacts visible |

Deliverables: working repo, 2-minute demo, short system & reliability brief.

**Reliability is 25%. Most teams will demo one happy path and score near zero on
it. The eval harness is not optional polish — it is the second-largest block of
points on the board.**

## Hard rules

1. **Never write a code path that only works on the happy path.** Every external
   write goes through the action layer in `enforcer/actions/` with an idempotency
   key and an entry in the action log.
2. **No wall-clock calls anywhere except `enforcer/core/clock.py`.** Everything
   reads the clock through that module so the seeded week can fast-forward.
   `datetime.now()` outside that file is a bug.
3. **The model never takes an action directly.** It returns a typed verdict or a
   typed plan. Deterministic code executes it. This is the whole reliability story,
   and it is also the structural defence against prompt injection.
3a. **Two-pass judging, always.** The extraction pass sees the image and NOT the
   user's claim. The comparison against the claim and the policy thresholds happens
   in deterministic code. Never send the claim and the image to the model together
   for a verdict — that is how the judge becomes a rubber stamp.
3b. **Null is a valid answer.** Every metric field is nullable, every reported
   number needs a source span, and a number reported from `unclear` evidence is an
   automatic ESCALATE. See `MODEL_RELIABILITY.md` §1.
3c. **User text never enters the system prompt.** Notes, claims, and display names
   go in the user turn inside delimiters, labelled untrusted.
3d. **Strip mentions from anything the model wrote before posting it to Discord.**
   Pass `allowed_mentions` disabling all mention parsing on every send.
4. **Every external integration sits behind an interface** in
   `enforcer/integrations/` with a real implementation and a fake implementation.
   The fakes are what make the eval harness and the offline demo possible.
5. **Dry-run mode must work end to end.** `ENFORCER_DRY_RUN=true` runs the entire
   flow, logs every intended action, and writes nothing externally.
6. **Cap the agent loop.** Max 12 tool calls per task, hard timeout 90s. A runaway
   loop on demo day is the most common way projects like this die.
7. **Do not add an integration that needs a credit card or an approval process.**
   See `docs/SETUP.md` for the approved list and why others were cut.
8. **`R1`, `R2`, `R4`, `R7` are decided in code, never by the model.** Image
   hashing, date arithmetic, threshold comparison, speed plausibility. The model
   only gets `R3`, `R5`, `R6`.
9. **Confidence is derived, not self-reported.** Compute `grounding_score()` from
   legibility, source spans, evidence quality and consistency. Gate escalation on
   it. See `MODEL_RELIABILITY.md`.
10. **No memory layers, no vector store, no consolidation loop.** 40 events over one
   week. The append-only ledger is the memory. Resist all suggestions otherwise.
11. **Secrets never reach a log, an embed, or a screenshot.** `.gitignore` before the
   first commit, not after.

## Stack

- **Python 3.11+**
- **discord.py** — gateway bot, no public URL needed, no ngrok, no deploy
- **AWS Bedrock, Converse API** (`boto3`, `bedrock-runtime` client) — the model layer.
  `qwen.qwen3-vl-235b-a22b` judges photo submissions; a Qwen text model runs the
  planner. Use `converse()`, never `invoke_model()`.
- **google-api-python-client** — Calendar
- **httpx** — Spotify
- **pydantic** — every model output is a validated schema
- **pytest** — eval runner lives here too

Model calls go through `enforcer/llm/client.py` and nowhere else. One function,
one place to swap providers if a model or region misbehaves on the day.

**Structured output is done with forced tool use, not JSON prompting.** Define a
single tool whose input schema is the pydantic model, set `toolChoice` to force it,
and read the arguments. This removes most parse failures at the source. Keep the
one repair retry anyway.

**Bedrock prerequisites:** model access must be enabled in the Bedrock console per
region, and the IAM principal needs `bedrock:InvokeModel`. Verify availability with
`aws bedrock list-foundation-models --region <r> | grep qwen` before assuming a
model ID works.

## Repo layout

```
enforcer/
  bot/            Discord gateway client, slash commands, embeds
  agent/          judge.py (does it count), planner.py (consequence plan)
  actions/        the only place external writes happen; idempotency + logging
  integrations/   calendar/, sheets/, spotify/, discord/ — real + fake impls
  core/           clock, policy loader, ledger, leaderboard, config
  llm/            client.py, prompts/
evals/
  cases/          labeled submissions (the eval set)
  fixtures/       seeded week for the demo
  run_evals.py    prints the precision/recall table
docs/
```

## What gets cut if we fall behind

Cut in this order, and never cut upward:

1. Spotify playlist
2. Appeals flow (design it in the brief, don't build it)
3. Sheets ledger (replace with a Discord embed showing the debt + UPI QR)
4. Google Calendar (replace with a Discord poll for scheduling)

**Never cut:** Discord loop, photo judging, leaderboard, eval harness, seeded week.
Those five are the project. Everything else is a bonus app.

## Integrations that were deliberately rejected

Do not suggest these; they were researched and ruled out.

- **Strava** — its API agreement bans showing one user's activity data to other
  users (kills the leaderboard) and bans use of Strava data with AI models (kills
  the judge). Both clauses, not one.
- **Google Places** — requires a billing account with a card.
- **Stripe** — India is invite-only for account signup; can't be verified in time.
- **Splitwise** — third-party API access now requires a Splitwise Pro subscription,
  which nobody in the group has. Replaced by Google Sheets.
- **A self-built expense service** — a service we wrote is not an *external* app and
  does not count toward the three-app requirement. Do not suggest this.
- **OpenTable / Resy / Yelp** — no public booking API available to a hackathon team.
- **Fitbit / Google Fit / Garmin / HealthKit** — deprecated, shut down, approval-
  gated, or no web API at all.

## Working style for this repo

- Small commits with real messages. Judges may look at the history.
- Write the fake implementation before the real one. It unblocks everything else.
- When in doubt, make the deterministic layer bigger and the model layer smaller.
- If you are about to add a feature not in `docs/BUILD_PLAN.md`, stop and check the
  clock instead.
