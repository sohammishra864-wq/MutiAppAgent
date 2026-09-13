# BUILD_PLAN.md — Sunday 13 September 2026

Build window: **9:30am – 4:00pm Pacific**. Judging 4:00–4:40pm. Awards 4:40–5:00pm.

Pacific times below. Convert to your local time and put them in your phone as
alarms tonight — including the abort triggers. You will not notice the clock while
you're deep in a bug.

---

## 09:00 – 09:30 · Opening

Listen for rule announcements, especially anything about pre-existing code. State
in your brief that setup and the eval set were prepared beforehand and that all
project code was written in the window. Disclosure is free; being caught not
disclosing is not.

---

## 09:30 – 10:30 · Skeleton

**Goal: a Discord slash command that returns a stubbed verdict.**

- `core/clock.py` (RealClock + SimulatedClock) — build this first, 15 lines
- `core/config.py` — typed settings from `.env`
- Pydantic schemas from `ARCHITECTURE.md`
- `integrations/*/fake.py` for all four — before any real implementation
- Discord gateway bot up, `/log` registered guild-scoped, accepting an image
  attachment, replying with a hardcoded verdict embed

**Checkpoint 10:30:** `/log` with a photo returns an embed. If not, you are behind.
Drop everything else and fix this; nothing works without it.

---

## 10:30 – 12:00 · The judge

**Goal: real verdicts on real photos.**

- `llm/client.py` — Bedrock Converse, forced tool use, one repair retry
- `llm/prompts/extract.md` — **image only, claim withheld** (two-pass, see
  `MODEL_RELIABILITY.md`)
- Deterministic pre-checks first: image hash duplicate lookup, EXIF date check.
  Only call the model if these pass.
- `agent/judge.py` — extract → validate observation → compare against policy in
  code → reason-code validator → `Verdict`
- Security basics while you're here: size/type cap on downloads, EXIF stripped
  after reading, `allowed_mentions` disabled on every Discord send
- Ledger append on every verdict
- Discord embed shows verdict, reason code, rationale, points

**Checkpoint 12:00:** you can submit a good photo and a bad photo and get correctly
different verdicts, and a photo with no legible numbers escalates rather than
inventing them. This is the heart of the project. Do not move on until it works.

---

## 12:00 – 13:00 · Simulation and leaderboard

**Goal: fast-forward a week and produce standings.**

- `evals/fixtures/week_01.json`
- `enforcer/simulate.py` driving SimulatedClock through the fixture
- `core/leaderboard.py` as a pure function over the ledger
- Weekly settlement: last place, tiebreaks, zero-submission rule
- Discord leaderboard embed + assign the `🐌 Last Place` role

**Checkpoint 13:00:** one command replays a week and announces a loser in Discord.

**You now have a demoable project.** Everything after this is upside. If you stop
here you still have a real submission.

---

## 13:00 – 14:00 · Consequences

**Goal: real writes in real apps.**

In this order, moving on the moment each works:

1. **Calendar** — freebusy across members, pick a slot, `events.insert` with
   `sendUpdates="all"`
2. **Google Sheets** — debt row in the ledger, plus the UPI QR in the embed
3. **Spotify** — playlist, themed by the planner

Every one through the action layer with idempotency keys. Log everything to
`run_log.jsonl`.

**Abort trigger 13:45:** if Calendar OAuth is still fighting you, stop. Switch to
the Discord poll fallback and take the remaining time for Sheets and Spotify,
which are far simpler. Do not let Google eat your afternoon.

---

## 14:00 – 14:45 · Evals

**Goal: numbers on a slide.**

- Wire up `evals/run_evals.py`
- Run the full 40-case set
- Run `--repeat 3` on a subset for variance
- **Screenshot the output table**
- Fix only the cheapest failures. Do not start a redesign at 2:30pm.
- Write down the failure patterns for the brief

**Checkpoint 14:45:** you have a printed metrics table and know your three weakest
case types.

---

## 14:45 – 15:30 · Demo

**Record early. Do not plan a live demo.**

Follow `docs/DEMO.md`. Expect three takes. Budget for the third being the good one.

---

## 15:30 – 16:00 · Ship

- System & reliability brief (template in `docs/RELIABILITY_BRIEF.md`)
- README with setup instructions and an architecture diagram
- Clean the repo, check no secrets committed, confirm `.env` is gitignored
- Submit with time to spare

**Do not write code after 15:30.** Something breaking at 15:50 with no time to fix
it is how good projects fail to submit at all.

---

## Cut order

When behind, cut from the top of this list:

1. Spotify
2. Appeals flow
3. Sheets → Discord embed with the UPI QR
4. Calendar → Discord poll

**Never cut:** Discord loop, judging, leaderboard, eval harness, seeded week.

---

## Rules for the day

- **Commit every 30 minutes.** Real messages. Judges may read the history.
- **When something takes more than 20 minutes, switch to the fake implementation
  and move on.** Come back if there's time. There usually isn't, and that's fine.
- **Do not refactor after 14:00.** Ugly and working beats clean and broken.
- **Eat lunch.** The 12:00–13:00 block is deliberately the lightest one.
