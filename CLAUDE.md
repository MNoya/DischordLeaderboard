# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Discord bot + public website for an MTGA community leaderboard called **LLU**. Players link their 17lands profile through Discord; the bot pulls draft data, computes a custom score, and ranks them within the current Magic set. Multi-server-capable (single shared leaderboard across all guilds the bot is invited to). Fully automated — no manual score submission.

- **Bot** (`bot/`): Python, `discord.py`, SQLAlchemy 2.0 + Alembic, deployed on Railway from `master`
- **Frontend** (`frontend/`): React 18 + Vite + TanStack Query + Tailwind, deployed on Cloudflare Pages at `https://dischord.pages.dev/leaderboard/`
- **Database**: Postgres — local Docker for dev, Supabase (project `yrecdosksgigpceholjl`) for prod

Spec documents live under `spec/` (original project spec, frontend contract, pod-draft design).

## Common commands

All Python commands assume the venv: `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/alembic`.

### Bot

```bash
# Run the bot (reads .env)
.venv/bin/python -u -m bot.main

# Tests (spins up a Postgres testcontainer)
.venv/bin/pytest bot/tests/
.venv/bin/pytest bot/tests/test_scoring.py::test_specific_thing  # single test

# Migrations (DATABASE_URL must be set)
.venv/bin/alembic upgrade head
.venv/bin/alembic check                # verify models match migrations
.venv/bin/alembic revision --autogenerate -m "msg"

# Seed + refresh against local DB
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/python -m bot.scripts.seed_sets
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/python -m bot.scripts.seed_local_players
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/python -m bot.scripts.refresh_stats --cache  # uses cache/17lands/
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/python -m bot.scripts.refresh_stats          # live fetch
```

### Frontend

```bash
cd frontend
npm run dev       # http://localhost:5173/leaderboard/
npm run build     # tsc -b && vite build → dist/
npm run preview
```

### Local Postgres (one-time setup, then `docker start dischord-pg`)

```bash
docker run -d --name dischord-pg -p 5433:5432 \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=devpw -e POSTGRES_DB=dischord \
  postgres:16-alpine
```

To wipe and re-seed:
```bash
docker exec dischord-pg psql -U postgres -d dischord -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
# then alembic upgrade head + seed_sets + seed_local_players + refresh_stats --cache
```

### Owner-only prefix commands (DM the bot)

- `!sync` — push slash-command schema changes to Discord. Run after editing any command's name/description/options. Body-only changes don't need it.
- `!refresh` — re-pull 17lands for active players against the active set's window, recompute scores, edit tracked leaderboard messages in place. Same code path as the periodic tick. For full-history reconciliation (formula change, retroactive set add, drift recovery) run `python -m bot.scripts.refresh_stats` from a console instead.

## Architecture

### Data flow

```
17lands API → bot/services/seventeenlands.py → bot/services/refresh.py
                                                       ↓
                                       draft_events (source of truth, additive)
                                                       ↓
                            player_stats + score tables (derived, rebuilt per refresh)
                                                       ↓
                                       Postgres (public_* curated views)
                                                       ↓
                              Frontend (supabase-js, anon key, browser-direct)
```

`draft_events` is keyed on `(player_id, seventeenlands_event_id)` and only grows — never wiped. `player_stats` and the score tables are recomputed from `draft_events` after every refresh, so a partial-window fetch is safe (writes only the events it returned; aggregates rebuild from the full history already on disk).

The bot is the only writer. The frontend reads through curated `public_*` Postgres views (no service-role key in the client). View row shapes are mirrored as camelCase TS types in `frontend/src/types/leaderboard.ts`; `frontend/src/data/adapter.ts` converts snake_case → camelCase.

### Set rotation — `bot/sets.py` is the single source of truth

```python
ACTIVE_SET_CODE = "SOS"
ALL_SETS = (SetSeed("FIN", ...), SetSeed("TLA", ...), SetSeed("ECL", ...), SetSeed("SOS", ...))
```

There is **no `is_current` flag on `sets`** and **no env var** for the active set. Rotation = bump the constant + push to master. Use the `/new-set <CODE>` Claude Code skill (`.claude/skills/new-set/`) to automate: it web-looks-up the official name + Arena release date, edits `bot/sets.py`, runs `seed_sets` + `refresh_stats`, and commits locally.

### Scoring formula — `bot/scoring.py`

Per queue group (Premier / Traditional / Sealed / Quick / LCQ Draft 1 / LCQ Draft 2):
```
group_score = trophies × group_points × trophy_rate × t/(t+2)
```
- `trophy_rate = trophies / events`
- `t/(t+2)` is a shrinkage prior (1 trophy in 1 event ≈ 33%, not 100%)
- LCQ Draft 2 is a special case: `wins × winrate × points`
- Total = sum across groups

After editing `DEFAULT_QUEUE_GROUPS`:
- Formula/weights only → `python -m bot.scripts.recompute_scores` (no 17L fetch)
- New format strings added → `python -m bot.scripts.rebuild_player_stats` (re-aggregates from existing `draft_events`, no 17L fetch)

The formula may diverge per set in the future — `DEFAULT_QUEUE_GROUPS` is global today but plausibly becomes per-set.

### Data model — key invariants

- **All `DateTime` columns are `DateTime(timezone=True)` (TIMESTAMPTZ).** Naive UTC was misinterpreted as local time by `discord.py`, shifting embed timestamps. Don't reintroduce naive datetimes.
- `players.seventeenlands_token` is nullable so `/pod-link-arena` can create lightweight pod-draft-only players without a 17lands profile.
- `player_stats` is unique per `(player, set, format, expansion)` and **fully derived** from `draft_events` — rebuilt via `DELETE + INSERT … SELECT GROUP BY` per touched (player, set) on every refresh. Alchemy variants like `Y26ECL` get their own row but bucket under `ECL` for scoring.
- `player_set_scores.last_calculated_at` is force-bumped every refresh (not just on score change) so the "Last updated" footer reflects refresh time.
- `draft_events` is the additive event log — one row per individual 17lands draft, keyed on `(player_id, seventeenlands_event_id)`. `set_id` is nullable so drafts in not-yet-registered expansions still persist; `/add-set` claims orphans by matching `expansion` to the new set's `code`. 17lands' case-encoded color string (`WBg` = WB main + green splash) is preserved verbatim in `colors`.
- `leaderboard_messages` tracks the bot's posted leaderboard per `(channel, set)` so `/leaderboard` delete-and-reposts (instead of duplicating) and `!refresh` edits in place. Stale rows get pruned on next edit attempt.

### Slash commands — `bot/commands/`

All commands work in server channels and DMs.

| Command | Purpose |
|---|---|
| `/leaderboard` | Current set leaderboard + persistent Join/Stats button view (registered via `bot.add_view()` at startup so buttons survive restarts) |
| `/stats [player]` | Per-player formula breakdown by queue group |
| `/join` | Sign-up DM walkthrough with 17lands token; per-user lock prevents duplicate flows |
| `/retire` | Pause participation (replies via DM) |
| `/relink` | Update 17lands token |
| `/exile` | Scrub stats + 17lands link, keep the row so pod history still references the player; button-confirm |
| `/help` | List commands |

Every interaction `send_message`/`followup.send` uses `ephemeral=(interaction.guild is not None)` so DMs don't get the "only you can see this" auto-expire badge.

### Frontend swap point — `frontend/src/data/api.ts`

Selects backend at module-load time via `useSupabase` from `data/supabase.ts`, driven by **`VITE_DATA_MODE`** (`prod` | `local` | `mock`; default `prod`). `prod`/`local` run `realApi.ts` against the prod public config or the `local_supabase_proxy` on `:3001`; `mock` runs the fixture-backed `mockApi.ts`. An explicit `VITE_SUPABASE_URL` + `VITE_SUPABASE_PUBLISHABLE_KEY` pair overrides prod/local for staging; `mock` always wins. The hook layer (`data/hooks.ts`) imports from `api.ts` and never knows which is live.

Vite `base: "/leaderboard/"` + React Router `basename="/leaderboard"` so the site matches the future LLU subpath today. SPA fallback for CF Pages is **`functions/_middleware.ts`** (a Pages Function), not `_redirects` — `_redirects 200`-rewrites are over-greedy on Cloudflare.

### CI — `.github/workflows/ci.yml`

On push/PR to `master`: spin up Postgres service container → `alembic upgrade head` → `alembic check` (catches model/migration drift) → `pytest bot/tests/`.

## Conventions (do not violate)

- **Branch is `master`**, never `main`.
- **Solo repo: commit directly to `master`** for routine changes. Branch + PR only for genuinely large changesets.
- **Bundle frontend changes; the user reviews locally before commit.** Commit backend first, leave frontend uncommitted until the user explicitly approves.
- **Tests target logic, not framework behavior.** No tests for "does Postgres work" or "does Alembic apply migrations" — focus on aggregator / scoring / signup branches / interaction handling.
- **Bot user-facing strings avoid first-person.** Use "Check your DMs" not "I sent you a DM". No "sign up" in user copy — use "join" / "joined" / "on the leaderboard" (internal Python identifiers like `process_signup`, `SignupKind` stay as-is).
- **Use the short set code (`SOS`) in user-visible strings**, not the full name ("Secrets of Strixhaven") — too long for embed slots.
- **Shared user-facing message strings live in `bot/commands/messages.py`** (the `MSG_*` constants), parallel to `descriptions.py` for command descriptions. Any string used by more than one command/listener goes there — never duplicate the same copy inline across modules, and don't park shared strings in a service module just because the first caller lived there. A string used by exactly one command may stay as a local `MSG_*` in that command's module; promote it to `messages.py` the moment a second caller needs it. Service modules (`bot/services/`) hold logic, not user copy.
- **Code comments: default to none.** If a comment runs longer than one line, delete the whole block — don't shrink it, delete it. The code is already self-explanatory if names are right. No periods at end of single-line comments (they're labels, not sentences). No parenthetical asides. Don't paraphrase library / decorator behavior at the declaration site — that belongs in upstream docs, not your file.
- **Commit style**: subjects start with uppercase; no manual line wrapping in description paragraphs; no `Co-Authored-By: Claude` or any AI trailer; plain senior-engineer prose, no AI/ML jargon. Use `- ` bullets when a commit has 2+ distinct changes.
- **Ask before saving memory** and **ask before architectural decisions** — surface structural questions rather than auto-deciding.

## Operational notes

- Local Postgres: container `dischord-pg` on host `:5433`, db `dischord`, user `postgres`, password `devpw`.
- Supabase prod pooler URL (with encoded password) lives in gitignored `.env.supabase`.
- 17lands cache: per-token JSONs at `cache/17lands/<token>__YYYY-MM-DD.json`. Use `refresh_stats --cache` for free re-aggregation, omit `--cache` for live fetch.
- Bot logs: `logs/bot.log` (gitignored). Audit log: append-only JSONL at `logs/events.jsonl`.
- Production guild: LLU community server, guild ID `775371722065051658`. Bot is `DisChord Bot#1519`, app ID `1466076574372724819`. Per-channel permission overrides can block `msg.edit` even when posting works via interaction-token auth — grant explicit channel access if `!refresh` fails on a tracked message.
- Discord fields in `bot/config.py` are optional so non-bot entry points (alembic CLI, seed scripts, tests) can construct `Settings` without them.
