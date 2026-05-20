---
name: fetch-player
description: Pull a player's 17lands drafts for the active set (or any set) and print them for debugging. Takes a Discord username or a raw 32-hex 17lands token. Reads against the prod Supabase DB to resolve usernames to tokens. Read-only — no DB writes, no commits. Use this when a player reports their event is missing from the leaderboard.
---

# fetch-player

Debug helper. Given a Discord username (or a raw 17lands token), pull that player's drafts from 17lands for a set, print the format breakdown and per-event detail, and flag any format strings that aren't in `bot.scoring.DEFAULT_QUEUE_GROUPS`.

## Arguments

`$ARGUMENTS` is `<identifier> [SET_CODE]`:

- `identifier` — Discord username (substring-matched against `players.discord_username` or `display_name`) OR a raw 32-hex 17lands token.
- `SET_CODE` (optional) — 3-4 letter set code. Defaults to `ACTIVE_SET_CODE` in `bot/sets.py`. Pass `ALL` for the player's full history with no expansion filter.

If no identifier is given, ask the user for one and stop.

## Workflow

### 1. Resolve `DATABASE_URL`

The script needs to hit the prod Supabase DB to look up tokens by username. Source it from `.env.supabase`:

```
export DATABASE_URL=$(grep SUPABASE_DB_URL .env.supabase | cut -d= -f2-)
```

If `.env.supabase` is missing, ask the user where the prod URL lives.

(If the user passed a raw 32-hex token instead of a username, the script still imports `bot.database`, so `DATABASE_URL` must be set to *something* valid — local Postgres is fine.)

### 2. Run the script

```
.venv/bin/python -m bot.scripts.fetch_player <identifier> [--set SET_CODE]
```

The script prints:

- Player display name (or `token …XXXX` if invoked with a raw token)
- Scope (set code + date window, or `all sets`)
- Total drafts
- Format breakdown (`format: count`) with a ⚠️ marker on any format not in `DEFAULT_QUEUE_GROUPS`
- Per-event detail sorted by `first_event_server_time`, with 🏆 on trophies and ⚠️ on unsupported formats

### 3. Interpret the output

- Format strings flagged ⚠️ are the actionable signal: 17lands is shipping events under a name our scoring doesn't recognize. Decide whether they belong in an existing group (likely `Sealed`) or warrant a new group, then update `bot/scoring.py` and the matching SQL CASE in a new alembic migration.
- Events with `🏆` are trophy runs (truthy `event_wins`).
- If `total drafts: 0`, the player has nothing logged for that set on 17lands — usually means the wrong set code, or the player didn't actually play.

### 4. Hand back

Summarize the findings to the user in 2-4 lines. Do not commit or push anything — this skill is read-only.

## Notes

- The 17lands API call is `GET https://www.17lands.com/user/data/{token}` with `start_date`, `end_date`, `expansion` from `ALL_SETS`. Excludes Alchemy variants for a single-set query; pass `--set ALL` to include them.
- Username matching is case-insensitive substring on both `discord_username` and `display_name`. If the match is ambiguous, the script picks the first hit and reports the resolved name — verify it's the right person before drawing conclusions.
- Raw token form (32 lowercase hex chars) skips the DB lookup entirely.
