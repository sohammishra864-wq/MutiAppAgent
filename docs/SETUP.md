# SETUP.md — Do all of this on Saturday

Every item is free and needs no payment card. Total time about 90 minutes.
None of it is "building the project", so it's clean to do before the window opens.

Work top to bottom. Item 1 is the highest-stakes unknown.

---

## 1. Verify Qwen (20 min) — DO THIS FIRST

Two things must work or the architecture changes.

**Enable model access first.** Bedrock console → Model access → Edit → enable the
Qwen models → Save. Per region. Nothing works until this is done. Then confirm the
model exists where you are:
`aws bedrock list-foundation-models --region $AWS_REGION | grep qwen`

**Vision.** Via the Converse API (`boto3` `bedrock-runtime`, `converse()`), send a
base64 image plus a text prompt to `qwen.qwen3-vl-235b-a22b`. Confirm it can read
numbers off a fitness-app screenshot (distance, duration, date). If it can't read
small text reliably, you need to know now, not at 11am Sunday.

**Tool calling.** Pass a `toolConfig` with two function definitions and confirm the
response parses cleanly into a `toolUse` block.

**Structured output.** Do NOT prompt for JSON. Define one tool whose input schema
is the `Verdict` model and set `toolChoice` to force it — the model must then return
schema-conforming arguments. Run it ten times and count clean parses. Keep one
repair retry in `llm/client.py` regardless.

Write down: which model IDs work in your region, and set an AWS budget alert before
you start looping — Bedrock is per-token and images are token-heavy.

**If vision is weak:** fall back to text-only judging where the user types the
metrics and the photo is treated as weaker corroboration. Still works, still an
agent, just a different prompt.

---

## 2. Discord (20 min)

1. Developer Portal → New Application → Bot → copy the token.
2. Enable **Message Content Intent** if you want to read raw messages. You probably
   don't — slash commands need no privileged intents and are less fragile.
3. OAuth2 URL generator → scopes `bot` + `applications.commands` → permissions:
   Send Messages, Embed Links, Attach Files, Create Public Threads, Send Messages
   in Threads, Manage Roles, Read Message History.
4. Invite the bot to a **private test server**.
5. Create the roles the agent will assign, e.g. `🐌 Last Place`. **The bot's own
   role must sit above any role it assigns in the server's role list, or the
   assignment silently fails with a 403.** This trips up almost everyone.
6. Get all your teammates/friends into the server tonight.
7. Register a throwaway slash command and confirm it appears. Guild-scoped commands
   register instantly; global commands can take up to an hour to propagate. **Use
   guild-scoped for the hackathon.**

Save: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_ID`.

---

## 3. Google Calendar (30 min — the one most likely to overrun)

No billing account and no card needed. Calendar is a Workspace API, not a Maps
Platform API. Only enable the Calendar API; the moment you enable a Maps API it
will start asking for billing.

1. console.cloud.google.com → new project.
2. APIs & Services → Library → enable **Google Calendar API**. Nothing else.
3. OAuth consent screen → **External** → publishing status **Testing**.
4. Add every participant's Gmail address as a **test user** (cap is 100).
5. Credentials → OAuth client ID → **Desktop app** (simplest local flow, no
   redirect URI hosting needed) → download `credentials.json`.
6. Scopes needed: `calendar.events` and `calendar.readonly` (freebusy).
7. **Run one full authorization with at least one friend's real account tonight.**
   Not your own. A friend's. This is the step that surprises people.

**Warn everyone in advance:** they will see a red "Google hasn't verified this app"
screen. They must click *Advanced* → *Go to [app name] (unsafe)*. If you don't
brief them, you will lose fifteen minutes on the day to confused people.

**The 7-day refresh token expiry** for Testing-mode apps is real but irrelevant to
a one-day event. Tokens issued Saturday work Sunday.

**Gotcha:** `events.insert` silently sends no invitations unless you pass
`sendUpdates="all"`. Set it.

Save: `credentials.json`, plus a `tokens/` directory with each person's token.

---

## 4. Google Sheets — the debt ledger (15 min)

Same Cloud project as Calendar. No new consent screen, no new client ID.

**Read this first.** Adding a scope invalidates tokens that were issued without it.
If you add `spreadsheets` to the shared scope list, every friend who already
authorized Calendar has to authorize again.

Avoid that: **keep two separate credential sets.**

- *Per-member tokens* — scope `calendar.readonly` only. Used for free/busy. Already
  done; don't touch them.
- *Ledger token* — your own account, scopes `spreadsheets` + `calendar.events`.
  Used to write the sheet and to create the party event as organizer.

Only you authorize the second one. Nobody else re-consents.

**Steps**

1. Cloud Console → APIs & Services → Library → enable **Google Sheets API** in the
   same project.
2. Create a spreadsheet by hand at sheets.google.com. Name it `Enforcer Ledger`.
3. Copy the ID from the URL: `docs.google.com/spreadsheets/d/<THIS_PART>/edit`.
4. Share it with your group (Viewer is enough) so it's a visible artifact in the demo.
5. Two tabs:
   - `debts` — header row:
     `idem_key | week_start | loser | amount | owed_to | status | created_at`
   - `verdicts` — optional mirror of the ledger, nice on camera
6. Run your auth flow once with the ledger scopes and save that token separately.

**Verify it works:**

```python
from googleapiclient.discovery import build

sheets = build("sheets", "v4", credentials=ledger_creds)
SHEET_ID = "..."

# idempotency: Sheets will duplicate happily, so check before writing
existing = sheets.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range="debts!A2:A"
).execute().get("values", [])
keys = {r[0] for r in existing if r}

key = "debt:2026-W37:sisanta"
if key not in keys:
    sheets.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range="debts!A:G",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [[key, "2026-09-14", "sisanta", 500,
                          "group", "unpaid", "2026-09-14T23:59:00+05:30"]]},
    ).execute()
```

Confirm the row appears in the browser. That's the integration done.

**Gotchas**
- `valueInputOption="RAW"` writes everything as a string. Use `USER_ENTERED` so
  numbers and dates are typed properly.
- Without `insertDataOption="INSERT_ROWS"` an append can overwrite a row below your
  range instead of inserting.
- Read-then-append is not atomic. Fine with one writer; note it in the brief.
- Quota is 60 write requests per minute per user. You will not get near it.

Save: `GOOGLE_SHEETS_ID`, and the path to the ledger token.

## 5. Spotify (10 min)

1. developer.spotify.com/dashboard → Create app.
2. Redirect URI: `http://localhost:8888/callback`.
3. Scopes: `playlist-modify-public`, `playlist-modify-private`.
4. Authorize once with your own account, save the refresh token.
5. Create a throwaway playlist via the API to confirm it works.

Playlist creation works on a free Spotify account. Playback control needs Premium,
which you don't need.

Save: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`.

---

## 6. The eval set (60–90 min, the highest-value item)

This is data and specification, not project code, so it's clean prep work — and
it's the single biggest scoring lever you have.

Collect **40 workout submissions**, roughly half legitimate and half not. Use your
own photos, friends' photos, screenshots, and deliberately constructed bad cases.
Label each one against `docs/POLICY.md`.

Full instructions and the file format are in `docs/EVAL.md`. Do this even if you
skip everything else on this list.

---

## 6b. Security prep (5 min)

Before the first commit:

```bash
printf '.env\nsecrets/\ndata/\n*token*.json\n__pycache__/\n.venv/\n' > .gitignore
```

Create a dedicated IAM user for Bedrock with `bedrock:InvokeModel` scoped to the
model ARNs you'll use. Not root. Set an AWS budget alert.

Full checklist in `docs/SECURITY.md`.

## 7. Repo scaffold (10 min)

```bash
mkdir enforcer && cd enforcer
git init
python -m venv .venv && source .venv/bin/activate
pip install discord.py pydantic httpx google-api-python-client \
            google-auth-oauthlib python-dotenv pytest boto3 qrcode[pil]
cp .env.example .env   # then fill it in
```

`boto3` is the Bedrock client. `qrcode` renders the UPI payment QR into the Discord
embed.

Copy `CLAUDE.md` and the whole `docs/` folder into the repo root now, so Claude Code
has the full context from its first message.

---

## Saturday night checklist

- [ ] Bedrock model access enabled; Qwen3-VL confirmed available in your region
- [ ] Qwen3-VL reads numbers off a fitness screenshot correctly
- [ ] Forced tool use returns schema-conforming arguments
- [ ] AWS budget alert set
- [ ] Discord bot in server, slash command responding, bot role above `Last Place`
- [ ] Calendar API enabled, consent screen in Testing, all test users added
- [ ] **One friend's account authorized successfully, end to end**
- [ ] Google Sheets row written from a script and visible in the browser
- [ ] Spotify test playlist created
- [ ] 40 labeled eval cases written
- [ ] Repo scaffolded, deps installed, `.env` filled, `CLAUDE.md` in place

If the Calendar item is not ticked by Saturday night, start Sunday assuming you'll
use the Discord poll fallback and treat Calendar as a stretch goal.
