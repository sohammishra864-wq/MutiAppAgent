# SECURITY.md — Secrets, Untrusted Input, Privacy, Abuse

This system holds five API credentials, ingests photos of people from an
adversarial user base, and posts public judgments about named individuals. That's a
real security surface for a weekend project.

None of what follows takes long. Most of it is a decision, not an implementation.

---

## 1. Secrets

**The rules:**

- `.env`, `secrets/`, `data/`, and `*token*.json` are in `.gitignore` **before the
  first commit**, not after.
- No credential ever appears in a log line, an exception message, a Discord embed,
  or a screenshot.
- `.env.example` holds keys with empty values. Never real ones.
- Use a dedicated IAM user for Bedrock. Not root, not your main user.

**Before you submit the repo, check the history, not just the working tree:**

```bash
git log -p | grep -iE "(sk-|AKIA|Bearer |client_secret|refresh_token)" | head
```

A secret committed and then deleted is still in the history and still leaked.
GitHub's secret scanning will catch a Discord bot token within minutes of a public
push, and Discord will invalidate it. Better to not need that.

**If a token does leak:** rotate immediately. Discord bot token from the portal,
AWS key from IAM, Google client secret from Cloud Console, Spotify from the
dashboard.

## 2. Least privilege

| Credential | Give it only |
|---|---|
| Discord bot | Send Messages, Embed Links, Attach Files, Create Public Threads, Send Messages in Threads, Manage Roles. **Not Administrator.** |
| Google per-member | `calendar.readonly` — free/busy only |
| Google ledger | `spreadsheets` + `calendar.events`, on your account only |
| AWS IAM | `bedrock:InvokeModel` on the specific model ARNs. Not `bedrock:*`, not `Resource: "*"` |
| Spotify | `playlist-modify-public`, `playlist-modify-private` |

The split Google credentials do double duty: they're least-privilege *and* they
mean adding the Sheets scope doesn't invalidate the tokens your friends already
granted.

## 3. Untrusted input

Everything a member submits is hostile until proven otherwise. That includes the
image, the note, the claimed metrics, and their Discord display name.

**Images**

- Cap the file size before download. Reject anything over ~10 MB.
- Validate the actual content type by reading the magic bytes, not by trusting the
  filename extension.
- Only fetch from Discord's CDN domains. **Never fetch an arbitrary URL a user
  posts** — that's an SSRF hole, and a bot on your laptop can reach your local
  network.
- Decompression limits when decoding. A small file can expand to a huge bitmap.
- Read EXIF for the date check, then **strip EXIF before storing**. It often
  contains GPS coordinates of someone's home.

**Text**

- The note field and display name never enter the system prompt. See
  `MODEL_RELIABILITY.md` §6.
- Cap note length. Truncate rather than reject.

**Model output is also untrusted.** The rationale gets posted publicly in Discord.
Before posting:

- Strip or escape `@everyone`, `@here`, and role mentions. Otherwise a successful
  injection turns your bot into a mass-ping tool.
- Escape markdown so output can't spoof the bot's own formatting.
- Use `allowed_mentions` on every send to explicitly disable mention parsing. This
  is one parameter and it closes the whole category.

## 4. Authorization

Easy to forget in a single-server project, and it's the first thing that breaks
when there are two servers.

- Verify the submitter is a member of the guild the submission is for.
- Verify an appeal author is the original submitter. Nobody appeals on someone
  else's behalf.
- Only the server owner (or a configured role) resolves an escalation.
- Every ledger entry carries `guild_id`, and every read filters on it. Cross-tenant
  data access is the one bug in this system that would be genuinely serious.

## 5. Privacy

These are photos of people, often in gyms, often at home, sometimes with location
data attached.

- **Minimise.** Store the image hash and a thumbnail. You don't need the full
  original after judging.
- **Strip EXIF** before anything is written to disk.
- **Scope access.** An image submitted in one server is never visible from another.
- **Never log image bytes.** Log the hash.
- **Retention.** State one. Ninety days is a reasonable default. Say it in the brief
  even if the hackathon build just deletes the folder afterwards.
- **The judge never comments on bodies, weight, appearance, or fitness level.** This
  is a hard rule in `POLICY.md`. It's the right call, and it's also the difference
  between a demo that lands and one that makes a room uncomfortable.

## 6. Abuse

Your users have a direct incentive to defeat the judge and they get immediate
feedback on what works. Design for that.

- **Rate limit submissions** to a few per member per day. Without this, `/log`
  becomes a brute-force oracle: resubmit until something passes.
- **Log rejected attempts.** The pattern of what people try is your hardening
  roadmap, and it makes a good line in the brief.
- **Rate limit appeals** too. One per submission, as the policy says.
- **Assume anything documented publicly will be probed.** That's fine. The mitigation
  is layered checks, not secrecy.

## 7. Operational

- Pin dependency versions. Do not `pip install` something unfamiliar at 2pm on
  demo day.
- Bound every outbound call with a timeout. Retry only 5xx and timeouts, never 4xx.
- Cap the agent loop: 12 tool calls, 90 seconds. A runaway loop is both a cost
  incident and a demo killer.
- Set an AWS budget alert before you start looping over the eval set.
- `ENFORCER_DRY_RUN=true` is the default in `.env.example` for a reason. Flip it
  deliberately.

## 8. Demo hygiene

Easy to get right, painful to get wrong, and it happens on camera.

- Close the AWS console, the Cloud Console, and any terminal with keys in
  scrollback before you record.
- Use a clean browser profile or a second desktop.
- Check the spreadsheet for real names and real phone numbers before it's on screen.
- The UPI QR in the demo should use a throwaway or test payee address, not your
  personal UPI ID. It will be visible frame by frame in a recording.
- Re-watch the recording once specifically looking for leaked credentials before
  you submit.

---

## What to say in the brief

Three sentences is enough:

> Submissions are treated as untrusted input: images are size- and type-validated,
> EXIF is read for date verification then stripped before storage, and user text
> never enters the system prompt. The model can only emit a typed verdict — it has
> no ability to take an action — so a successful prompt injection yields at most one
> wrong judgment rather than an unauthorised external write. Model output is
> mention-stripped before it is posted publicly.

That paragraph answers a question most teams won't have thought about at all.
