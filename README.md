# The Enforcer

Hey there! I'm Soham. I built this fun-to-use multi-app agent that connects Google Calendar, Google Sheets, Discord, and Spotify. The motive was to build a great agent and have fun while doing it — and I think this turned out to be a good one. I've attached detailed info and a video demo link below. Thank you!

---

**A multi-app AI agent that judges fitness accountability and executes real consequences.**

Members of a Discord server log workouts with photo proof. The Enforcer judges each submission against a written policy using vision AI, maintains a weekly leaderboard, and when the week ends — **takes action**: the last-place member owes the group a party. The agent finds a time everyone is free, creates a Google Calendar invite, records the debt in Google Sheets, and builds the loser a shame playlist on Spotify.

> The point is not the leaderboard. The point is that a system makes a **judgment call** on ambiguous evidence and then **takes real action across four apps**.

---

## Architecture

```
Discord /log  ──►  Judge (Qwen3-VL 235B on Bedrock)  ──►  Verdict (typed)
                                                  │
                                                  ▼
                                             Ledger (append-only JSONL)
                                                  │
                                  weekly trigger  ▼
                                             Leaderboard
                                                  │
                                                  ▼
                                        Planner (consequence plan)
                                                  │
                                  ┌───────────────┼───────────────┐
                                  ▼               ▼               ▼
                           Google Calendar   Google Sheets     Spotify
                          (find slot, invite)  (debt ledger)  (shame playlist)
                                  └───────────────┼───────────────┘
                                                  ▼
                                           Discord announcement
                                             + role assignment
```

### Two-pass judging

The model never rubber-stamps a claim. Judging is split so anchoring bias can't leak in:

| Pass | Input | Output |
|------|-------|--------|
| **Extract** | Image only (claim withheld) | `ObservedMetrics` — what the model actually sees |
| **Compare** | Deterministic code | Verdict + reason code (thresholds from `POLICY.md`) |
| **Disambiguate** | Model (only if needed) | Activity-type plausibility check |

Seven reason codes (`R1`–`R7`) cover duplicates, stale submissions, identity mismatch, below-threshold, activity mismatch, unverifiable evidence, and implausible metrics. Four of these (`R1`, `R2`, `R4`, `R7`) are decided entirely in code — the model only handles the genuinely fuzzy questions.

### The one design decision that matters

**The model produces typed output. Deterministic code takes the actions.**

The judge returns a `Verdict`. The planner returns a `ConsequencePlan`. Neither calls an API. The action layer in `enforcer/actions/` reads the plan and executes it with idempotency keys, retry logic, and an append-only audit log. This is what makes the system reliable and testable.

---

## Apps integrated

| App | What it does | Auth |
|-----|-------------|------|
| **Discord** | Slash commands, photo submissions, embeds, role assignment | Bot token |
| **Google Calendar** | FreeBusy lookup across members → event creation with invites | OAuth 2.0 |
| **Google Sheets** | Debt ledger (replaces Splitwise, which now requires Pro) | OAuth 2.0 |
| **Spotify** | Shame playlist creation + track search | OAuth 2.0 refresh token |

Every integration sits behind a `Protocol` with a live and a fake implementation. The fakes power the eval harness and offline demo — flip one env var to switch.

---

## Eval harness

40 labeled test cases across easy and hard difficulties. The eval runner prints:

- **Overall accuracy** and per-verdict confusion matrix
- **ACCEPT precision/recall** — the numbers that matter for accountability
- **Per-reason-code accuracy** (R1–R7)
- **Grounding score vs. model confidence** — does our derived score beat self-reported confidence?
- **Verdict stability** across repeated runs
- **Latency p50/p95**

```bash
python -m evals.run_evals                     # full suite
python -m evals.run_evals --case case_012     # single case
python -m evals.run_evals --repeat 3          # stability test
```

---

## Reliability defenses

| Defense | Where |
|---------|-------|
| Two-pass judging (extract vs. compare) | `agent/judge.py` |
| Derived grounding score, not self-reported confidence | `core/validation.py` |
| Nullable metrics — unclear evidence → auto-ESCALATE | `core/schemas.py` |
| Prompt injection detection on user text | `core/injection.py` |
| User text never in system prompt; mentions stripped | `bot/bot.py` |
| Idempotency keys on every external write | `actions/base.py` |
| Forced tool use for structured output (no JSON parsing) | `llm/client.py` |
| Hard cap: 12 tool calls, 90s timeout | `core/config.py` |
| Append-only ledger — never mutate, never delete | `core/ledger.py` |
| Injected clock — deterministic replay for evals | `core/clock.py` |
| Dry-run mode end to end | `ENFORCER_DRY_RUN=true` |

---

## Quick start

```bash
# 1. Clone and install
git clone <repo-url> && cd MutiAppAgent
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Fill in: DISCORD_BOT_TOKEN, AWS credentials, Google OAuth, Spotify tokens

# 3. Run offline simulation (no credentials needed)
python -m enforcer.simulate evals/fixtures/seeded_week.json

# 4. Run the eval suite (needs Bedrock access)
python -m evals.run_evals

# 5. Run the live bot
python -m enforcer
```

### Discord commands

| Command | Description |
|---------|-------------|
| `/log <activity> [duration] [distance]` | Submit a workout with photo proof |
| `/leaderboard` | Show current weekly standings |
| `/consequence` | Trigger end-of-week consequence chain (admin) |

---

## Repo structure

```
enforcer/
  bot/              Discord gateway, slash commands, rich embeds
  agent/            judge.py (two-pass verdict), planner.py (consequence plan)
  actions/          The only place external writes happen — idempotency + audit log
  integrations/     calendar/ sheets/ spotify/ discord/ — live + fake per service
  core/             clock, config, ledger, leaderboard, schemas, validation, injection
  llm/              Bedrock client, prompt templates
evals/
  cases/            40 labeled submission cases (JSON + images)
  run_evals.py      Precision/recall table, confusion matrix, stability
docs/
  ARCHITECTURE.md   System design and schema reference
  POLICY.md         The fitness accountability rules the judge enforces
  MODEL_RELIABILITY.md   Hallucination taxonomy and defense strategies
  SECURITY.md       Prompt injection, mention stripping, trust boundaries
  SYSTEM_DESIGN.md  Why the architecture is shaped this way
```

---

## Stack

- **Python 3.11+**
- **discord.py** — gateway bot, no public URL needed
- **AWS Bedrock** — `qwen.qwen3-vl-235b-a22b` (vision judge) + Qwen text (planner), via Converse API
- **google-api-python-client** — Calendar and Sheets
- **httpx** — Spotify Web API
- **pydantic** — typed schemas for every model output

---

## Demo

[Watch the 2-minute demo](https://drive.google.com/file/d/1-k57WavtZI0ihv8aNGBavYrv7938bIiH/view?usp=sharing)

---

## Team

Built solo by **Soham** for the **Multi-App AI Agent Hackathon** (September 2026).

---

## License

MIT
