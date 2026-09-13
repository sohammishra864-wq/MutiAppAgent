# 2-Minute Demo Script

**Total time: ~2:00.** Practice twice before recording. Keep terminal font large.
Pre-open all tabs/windows before you hit record.

---

## Pre-recording setup

1. Terminal open in `MutiAppAgent/` — large font, dark background
2. VS Code/editor open with `enforcer/agent/judge.py` visible (two-pass flow)
3. Have the Discord bot channel visible (if live) or screenshot of a Discord embed ready
4. Clear `data/ledger.jsonl` and `data/run_log.jsonl` so logs start clean

---

## SCENE 1: The Problem (0:00 – 0:20)

**Show:** Title slide or just talk over a Discord screenshot.

**Say (paraphrase, don't read robotically):**

> "We built The Enforcer — a fitness accountability agent. Five friends in a
> Discord server log workouts with photo proof all week. At the end of the week,
> last place owes the group a party.
>
> The agent doesn't just track scores. It judges each photo with vision AI,
> maintains a leaderboard, and then executes the consequence — books a calendar
> event, logs the debt in Google Sheets, and builds the loser a shame playlist
> on Spotify."

---

## SCENE 2: Submission + Judgment (0:20 – 0:55)

**Show:** Terminal. Run the offline simulation.

```bash
python -m enforcer.simulate evals/fixtures/week_01.json --offline
```

**As it runs, narrate:**

> "Here's a full week fast-forwarded. Five members, 15 submissions. Watch the
> verdicts — Alice's morning run: ACCEPT, 3 points. Dave's 10-minute jog:
> REJECTED, below the 20-minute threshold. Eve's 40-minute walk: REJECTED,
> didn't hit 5 km."

**Pause on the output showing standings + loser.**

> "Dave ends last with just 0 points — he's on the hook."

---

## SCENE 3: Two-Pass Judging (0:55 – 1:15)

**Show:** Switch to editor — `enforcer/agent/judge.py`, scroll to the two-pass flow.

**Say:**

> "The judge isn't one model call. Pass one sends only the image to the vision
> model — the user's claim is withheld, so the model can't anchor on it. It
> extracts what it actually sees: activity type, duration, distance, date.
>
> Pass two is deterministic code — it compares the extracted metrics against
> policy thresholds. No model involved. This is how we prevent the AI from
> becoming a rubber stamp."

---

## SCENE 4: Consequence Chain (1:15 – 1:35)

**Show:** Terminal. Point at the action log output from the simulation.

**Say:**

> "When the week ends, the consequence chain fires: Google Calendar — find a
> free slot, create the party event. Google Sheets — log the debt. Spotify —
> build a shame playlist. Every action has an idempotency key, so re-running
> the week doesn't create duplicates."

**Show:** Quick scroll of `data/run_log.jsonl` to show the audit trail.

> "Every action gets logged — kind, key, success, latency. If Spotify times
> out, Calendar and Sheets still complete. The system reports what worked and
> what didn't."

---

## SCENE 5: Eval Harness (1:35 – 1:55)

**Show:** Terminal.

```bash
python -m evals.run_evals --difficulty easy
```

**(Or show a pre-recorded screenshot of the eval output table if you can't run Bedrock live.)**

**Say:**

> "We have 40 labeled eval cases — easy and hard. The runner prints precision,
> recall, a confusion matrix, per-reason-code accuracy, and grounding score vs
> model confidence. This isn't a demo of one happy path — we measured the system."

**Point at the numbers.** If you have real results, quote them. If offline, say:

> "In our last run: [X]% accuracy, [Y]% ACCEPT precision, [Z] grounding
> violations across 40 cases."

---

## SCENE 6: Closing (1:55 – 2:00)

**Say:**

> "Four real apps, vision-based judgment with hallucination defenses, typed
> schemas end to end, and an eval harness with 40 cases. The Enforcer."

---

## Tips

- **Speed:** You have 2 minutes. If a scene runs long, cut Scene 3 to one sentence.
- **Don't show code for long.** Flash it, explain the point, move on.
- **Terminal output is your demo.** The simulation running + results printing is more convincing than slides.
- **If you can show a real Discord embed:** even one screenshot of the bot's verdict embed is worth 10 seconds of your time.
- **Pre-record the eval output** if Bedrock is slow — paste a screenshot and talk over it.
- **End strong.** "Four real apps" + "40 eval cases" is the mic drop. Judges remember the last thing.
