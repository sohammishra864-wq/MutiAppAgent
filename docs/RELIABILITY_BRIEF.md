# System & Reliability Brief — The Enforcer

*Template. Fill the bracketed parts on the day. Keep it to roughly one page; this
is a brief, not a report. Write it at 15:30 when the numbers are final.*

---

## What it does

A group fitness accountability agent. Members log workouts in Discord with photo
proof. The agent judges each submission against a written policy, maintains a
weekly leaderboard, and executes the consequence for last place across Google
Calendar, Google Sheets and Spotify.

## Apps connected

| App | Actions taken |
|---|---|
| Discord | Reads submissions, posts verdicts, opens appeal threads, assigns roles |
| Google Calendar | Queries free/busy across members, creates the event, sends invites |
| Google Sheets | Appends the debt row to the group's shared ledger |
| Spotify | Creates and populates the playlist |

## How it works

Qwen3-VL on AWS Bedrock reads each submission image and returns a **typed verdict**, never an
action. Deterministic code executes. Duplicate and stale-date checks run before the
model is called at all, using image hashing and EXIF, so the model only handles
judgments that genuinely need judgment.

At week end a planner produces a `ConsequencePlan`, and the action layer executes it
step by step. Every external write carries a content-derived idempotency key and
appends to a JSONL audit log.

## Reliability

**Design**
- Model output is constrained by forced tool use against a pydantic schema, with
  one repair retry
- **Two-pass judging**: the extraction pass never sees the member's claim, so the
  judge cannot anchor on it; the comparison against policy thresholds is arithmetic
- Every reported metric requires a source span; metrics claimed from unclear
  evidence force an escalation
- Reason codes are validated against the observation in code and rewritten when
  inconsistent
- Duplicate, stale-date, threshold and plausibility checks are fully deterministic;
  the model only handles the three genuinely fuzzy reason codes
- Asymmetric thresholds: a cheating accusation requires 0.90 confidence, other
  verdicts 0.75
- Every external write is idempotent; re-running a week creates no duplicates
- `ENFORCER_DRY_RUN` runs the full chain writing nothing externally
- Agent loop capped at 12 tool calls and 90 seconds
- Consequence chain continues on partial failure and reports what didn't complete
- A simulated clock makes an entire week replayable deterministically

**Evaluation**

40 hand-labeled submissions, labeled by us against the policy document, not by a
model.

| Metric | Result |
|---|---|
| Overall verdict accuracy | [ ]% |
| Precision on ACCEPT | [ ]% |
| Recall on ACCEPT | [ ]% |
| Escalation rate | [ ]% |
| Verdict stability across 3 identical runs | [ ]% |
| p50 / p95 judgment latency | [ ] / [ ]s |
| Grounding violations (no source span / unclear+metrics) | [ ] |
| Reason codes rewritten by the validator | [ ] |
| Prompt injection attempts caught | [ ] / [ ] |

Per-reason-code accuracy: [table]

## Where it fails

1. **[Weakest reason code]** at [ ]%. [Why. Be specific.]
2. **[Second weakness].** [Why.]
3. **[Third.]**

[One sentence on what you'd do with another day.]

## Security posture

Submissions are treated as untrusted input: images are size- and type-validated,
EXIF is read for date verification then stripped before storage, and user text never
enters the system prompt. The model can only emit a typed verdict — it has no
ability to take an action — so a successful prompt injection yields at most one
wrong judgment rather than an unauthorised external write. Model output is
mention-stripped before it is posted publicly. Credentials are least-privilege and
split, with per-member Google tokens limited to free/busy reads.

## Deliberate scope limits

- Fitness data is submitted manually rather than pulled from Strava. Strava's API
  agreement prohibits both displaying one member's activity data to another
  (which a leaderboard requires) and processing Strava data with AI models (which
  the judge requires). Manual submission with photo proof is the compliant design,
  not a shortcut.
- Party venue is chosen from a configured list rather than a live places API.
- Appeals are [built / designed but not built].

## What was prepared before the window

Account registration, API credentials, OAuth consent configuration, and the labeled
evaluation set. All project code was written during the build window.
