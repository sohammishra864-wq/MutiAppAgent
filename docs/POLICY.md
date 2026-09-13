# POLICY.md — House Rules

This file is the agent's rubric. It is loaded at runtime by
`enforcer/core/policy.py` and passed into the judge prompt. It is also the ground
truth your eval labels are scored against.

Treat it as a spec, not prose. If the judge and a human disagree on a case, one of
two things is true: the model was wrong, or **this document is ambiguous**. Fix
whichever it is. Ambiguity here is the most common source of eval noise.

---

## 1. What earns points

A **valid submission** earns points. One person can earn points at most **once per
calendar day**, in the group's timezone (`Asia/Kolkata`).

| Activity | Minimum to count | Points |
|---|---|---|
| Run / jog | 20 min or 3 km | 2 |
| Cycle | 30 min or 8 km | 2 |
| Gym / strength session | 30 min | 2 |
| Swim | 20 min | 2 |
| Walk / hike | 45 min or 5 km | 1 |
| Sport (football, badminton, etc.) | 30 min | 2 |
| Home workout / yoga | 25 min | 1 |

Bonus: +1 for any session before 07:00 local. Because it's funny and it rewards the
behaviour the group actually wants.

A day with no valid submission scores **0**. There is no penalty beyond zero.

---

## 2. Required evidence

Every submission must include:

- **An image.** A tracker screenshot, a gym mirror photo, a smartwatch face, a
  photo of the route or venue.
- **A claimed activity type** from the table above.
- **A claimed duration or distance.**

The agent's job is to decide whether the image is consistent with the claim.

---

## 3. Verdicts

The judge returns exactly one of three verdicts.

### ACCEPT
The evidence is consistent with the claim and meets the threshold.

### REJECT
One of the reason codes below applies. The reason code must be stated.

### ESCALATE
The judge is genuinely uncertain, or the evidence is ambiguous in a way a human
should settle. Escalation opens an appeal thread. **Escalation is a legitimate
outcome, not a failure.** A system that escalates 10% of cases and is right on the
rest is far better than one that guesses confidently on everything.

Escalate when confidence is below **0.75**, or when a REJECT would rest on
something the member could easily explain (a dead watch, an indoor session with no
GPS).

---

## 4. Rejection reason codes

These double as your eval taxonomy. Report per-code accuracy, not just an overall
number.

| Code | Meaning | Example |
|---|---|---|
| `R1_DUPLICATE` | Same activity already submitted | Same screenshot posted twice, or the same session claimed by two people |
| `R2_STALE` | Evidence is from outside the claimed day | A screenshot dated three days ago |
| `R3_NOT_SUBMITTER` | Evidence belongs to someone else | A screenshot of a friend's run, a photo pulled off the internet |
| `R4_BELOW_THRESHOLD` | Real but doesn't meet the minimum | A genuine 12-minute jog |
| `R5_MISMATCH` | Image doesn't match the claimed activity | Claims a 10 km run, image shows a treadmill at 0.8 km |
| `R6_UNVERIFIABLE` | No metrics and no usable context | A blurry selfie with no numbers, no location, no equipment visible |
| `R7_IMPLAUSIBLE` | Metrics are not physically credible | 42 km at 3:10/km pace; a "run" averaging 35 km/h |

---

## 5. Judging guidance

**Be generous about form, strict about substance.** A bad photo of a real workout
is fine. A perfect screenshot of someone else's workout is not.

**Prefer ESCALATE over a confident REJECT when the member has a plausible
explanation available.** The social cost of falsely accusing someone is much higher
than the cost of asking.

**Prefer REJECT over ACCEPT when evidence is absent entirely.** No image, no
numbers, no context is `R6_UNVERIFIABLE`, not a benefit of the doubt.

**Watch for the cheap fakes specifically:**
- A photo of a phone screen showing another phone (re-photographed screenshot)
- Stock or web imagery (unnaturally clean, watermarks, no personal context)
- Cropped screenshots where the date or the distance has been cut out — treat a
  conspicuous crop over the key metric as suspicious, not neutral
- Metrics in the image that contradict the typed claim; **the image wins**

**Never infer anything about a person's body, health, weight, or fitness level.**
The judge rules on whether an activity happened and met a threshold. Nothing else.
Do not comment on appearance. This is both the right call and the thing that would
make the demo land badly in a room.

---

## 6. Weekly settlement

At the end of the week (Sunday 23:59 local):

1. Sum each member's points.
2. Lowest total is **last place**. Ties are broken by fewest valid submission days,
   then by the earliest first submission of the week (rewarding the one who at
   least started).
3. A member with **zero** valid submissions all week is last place regardless of
   ties.
4. Last place owes the group a party, capped at **₹500 per attending member**.
5. The agent then executes the consequence chain (see `docs/ARCHITECTURE.md`).

---

## 7. Appeals

A member may appeal a REJECT once, in the thread the agent opens. They may add
evidence. The agent re-judges with the original submission plus the new evidence
plus the appeal text.

An appeal can move REJECT → ACCEPT or REJECT → ESCALATE. It cannot move ACCEPT →
REJECT; once points are awarded they stand. This keeps the ledger append-only and
avoids a whole class of state bugs.

If the re-judge still escalates, the server owner decides with a button.

---

## 8. Amending this file

If you change a threshold or add a reason code, **re-run the eval set** before
trusting any prior numbers. The labels are tied to this version of the policy.

Policy version: `v1`. Bump it on any change and record the version in every
verdict.
