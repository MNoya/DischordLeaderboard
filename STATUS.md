# DischordLeaderboard — Status Snapshot

Updated 2026-05-02. Backend + Discord bot are functional end-to-end against live 17lands data. Frontend not started.

---

## What this project is

A Discord bot + (planned) public website for an MTGA community leaderboard. Players link their 17lands profile through Discord; the bot pulls their draft data, computes a score using a custom formula, and ranks them within the current Magic set. Single Discord server. Fully automated — no manual score submission.

---

## Tech stack

| Layer | Tech | Status |
|---|---|---|
| Discord bot | `discord.py>=2.3` | Running locally |
| Database | Postgres (local Docker now, Supabase planned) | `dischord-pg` container on `:5433` |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | One initial migration `e8c3a1b2f0d4_initial_schema` |
| Config | `pydantic-settings` from `.env` | `bot/config.py` |
| 17lands client | `requests` + custom rate limiter + JSON file cache | `bot/services/seventeenlands.py` |
| Scoring | Custom formula (legacy ECL formula adapted) | `bot/scoring.py` |
| Tests | `pytest` + `testcontainers[postgres]` + `responses` | 88 passing |
| CI | GitHub Actions | `.github/workflows/ci.yml` (master branch) |
| Frontend | React + Vite | NOT STARTED |
| Deployment | Railway (bot), Netlify (frontend), Supabase | NOT STARTED |

---

## Repo layout

```
.
├── alembic/                      # DB migrations
│   ├── env.py                    # reads DATABASE_URL via bot.config.settings
│   └── versions/e8c3a1b2f0d4_initial_schema.py
├── alembic.ini
├── bot/
│   ├── config.py                 # pydantic-settings: DATABASE_URL, DISCORD_*, CURRENT_SET_CODE, public_site_url
│   ├── database.py               # SessionLocal + run_migrations()
│   ├── models.py                 # Player, MagicSet, PlayerStats, PlayerSetScore
│   ├── scoring.py                # QueueGroup, DEFAULT_QUEUE_GROUPS, compute_score, compute_score_breakdown
│   ├── audit.py                  # Append-only JSONL event log → logs/events.jsonl
│   ├── main.py                   # Bot entry point; owner-only !sync and !refresh prefix commands
│   ├── commands/
│   │   ├── signup.py             # /join (slash)
│   │   ├── signout.py            # /retire (slash)
│   │   ├── update_profile.py     # /relink (slash)
│   │   ├── delete_account.py     # /exile (slash, DM-only)
│   │   ├── leaderboard.py        # /leaderboard (slash) + Stats link button
│   │   ├── stats.py              # /stats (slash)
│   │   └── help.py               # /help (slash)
│   ├── services/
│   │   ├── seventeenlands.py     # SeventeenLandsClient + MinIntervalLimiter + aggregate_for_set
│   │   └── refresh.py            # refresh_player, refresh_active_players, recompute_player_set_score
│   ├── scripts/
│   │   ├── seed_initial_players.py  # seeds MagicSets + Players from legacy/user_ids.py
│   │   ├── refresh_stats.py         # CLI: pull 17lands + write PlayerStats + recompute scores
│   │   └── recompute_scores.py      # CLI: recompute PlayerSetScore from existing PlayerStats (no 17L fetch)
│   └── tests/
│       ├── conftest.py           # Postgres testcontainer fixture
│       ├── test_seventeenlands.py
│       ├── test_refresh.py
│       ├── test_scoring.py
│       ├── test_signup.py
│       ├── test_signout.py
│       ├── test_update_profile.py
│       ├── test_delete_account.py
│       └── test_leaderboard.py
├── legacy/                       # Original spreadsheet-era code (reference; aggregator + scoring formula)
│   ├── aggregator.py
│   ├── leaderboard.py
│   ├── main.py
│   └── user_ids.py               # PLAYERS list (gitignored)
├── cache/17lands/                # Per-token JSON cache for dev (gitignored)
├── logs/                         # bot.log + events.jsonl (gitignored)
├── .github/workflows/ci.yml      # alembic upgrade head + alembic check + pytest on master
├── .env                          # DATABASE_URL, DISCORD_BOT_TOKEN, DISCORD_GUILD_ID (gitignored)
├── mtga-leaderboard-spec.md      # Original project spec
└── STATUS.md                     # This file
```

---

## Slash commands (Discord)

All commands work in both server channels and DMs with the bot, **except** `/exile` which is DM-only.

| Command | Purpose | Visibility |
|---|---|---|
| `/leaderboard` | Show current set leaderboard (top 8 + your rank) | Server + DM |
| `/stats [player]` | Per-player formula breakdown by queue group | Server + DM |
| `/join` | Sign up — DM flow with 17lands token | Server + DM |
| `/retire` | Pause participation (stats kept) | Server + DM |
| `/relink` | Update 17lands token | Server + DM |
| `/help` | List commands | Server + DM |
| `/exile` | Permanently delete account + stats | DM only |

**Owner-only prefix commands** (text, in DM with the bot, invisible to others):
- `!sync` — push slash command changes to Discord. Run after editing any command.
- `!refresh [SET_CODE]` — pull stats from 17lands for active players, DMs invalidated tokens.

`!refresh` defaults to `settings.current_set_code` (env var). Pass a code to refresh historical sets.

---

## Data model

```
players (id, discord_id?, discord_username?, display_name, seventeenlands_token, ...)
sets (id, code, name, start_date, end_date)
player_stats (id, player_id, set_id, format, expansion, events, wins, losses, games_played, trophies, last_fetched_at)
  UNIQUE (player_id, set_id, format, expansion)
player_set_scores (id, player_id, set_id, score, trophies, last_calculated_at)
  UNIQUE (player_id, set_id)
```

- `players.discord_id` is **nullable** so seeded legacy players can exist before linking via `/join`.
- `player_stats` is per-(player, set, format, expansion) — Alchemy variants like `Y26ECL` get their own row but bucket under `ECL` for scoring.
- `player_set_scores` is the pre-computed total written by `refresh_player`. Read by `/leaderboard` for fast queries. Recompute via `recompute_scores.py` after scoring formula changes.
- No `is_current` flag on sets — current set is resolved from `settings.current_set_code` env var.

---

## Scoring formula

Carried over from the legacy ECL spreadsheet, generalized into queue groups.

```
For each queue group (Premier / Traditional / Sealed / Quick / LCQ Draft 1 / LCQ Draft 2):
  group_score = trophies × group_points × trophy_rate × t/(t+2)
Total = sum of group scores
```

- `trophy_rate = trophies / events`
- `t/(t+2)` is the shrinkage prior — penalizes tiny samples (1 trophy in 1 event ≈ 33%).
- LCQ Draft 2 uses a special rule: `wins × winrate × points` (counts wins instead of trophies).

Group config in `bot/scoring.py::DEFAULT_QUEUE_GROUPS`. Adding/changing groups requires:
1. Edit the tuple.
2. If new format strings were added (e.g., a new LCQ format kicks in), run `refresh_stats.py --cache` to re-aggregate from cached 17lands data (no live fetch needed).
3. If only weights/formula changed, run `recompute_scores.py` (no fetch at all).

---

## Operational state

**Postgres**: local Docker container `dischord-pg` on host port 5433. DB name `dischord`, user `postgres`, password `devpw`.
- Drop + recreate: `docker exec dischord-pg dropdb -U postgres dischord && docker exec dischord-pg createdb -U postgres dischord`

**Bot**: started with `.venv/bin/python -u -m bot.main`. Logs to `logs/bot.log` and console.

**Seeded data**: 11 players from `legacy/user_ids.py`, 2 sets (ECL historical, SOS current). Run `python -m bot.scripts.seed_initial_players`.

**17lands cache**: 11 player JSONs at `cache/17lands/<token>__2026-04-21.json`. Re-fetch live with `python -m bot.scripts.refresh_stats` (no `--cache`).

**Live SOS leaderboard** (current data, real 17lands pulls):
```
1. Oophies       53.4  19   ← Trad grinder
2. Elfandor      24.7  12
3. Doctormagi    17.7   8
4. jimbo         17.0   9
5. Sam Black      7.7   3
6. theburnin8or   4.9   5
7. Noya           1.9   3
8. GLP            0.7   1
```
(LavaAxe, Golgotha, wav'painter present but with 0 score — haven't drafted SOS yet.)

---

## Outstanding tasks

| # | Task | Status | Notes |
|---|---|---|---|
| 27 | Build React + Vite frontend | pending | The big remaining slice |
| 29 | Commit current working tree | pending | ~50 untracked files |
| 30 | Production deployment (Supabase + Railway + Netlify) | pending | Supabase + Railway can land before frontend; Netlify needs frontend |

**Optional micro-cleanup** (no task tracked):
- Real set display names instead of `name="ECL"` / `name="SOS"` placeholders in `seed_initial_players.py`.
- Rank movement arrows (▲▼) inspired by scoreboards.dev — needs a previous-rank snapshot table.

**Deferred / parked decisions** (resolved later when relevant):
- Per-set scoring config (currently `DEFAULT_QUEUE_GROUPS` is global; per-set future-proofing not built).

---

## Conventions / things to keep doing

- **Tests target logic, not framework behavior.** No tests for "does Postgres work" or "does Alembic apply migrations." Tests focus on aggregator / scoring / signup-flow branches / etc. (memory: `feedback_test_logic_not_integrity.md`)
- **Bot user-facing strings avoid first-person.** No "I sent you a DM" — use "Check your DMs" instead. (memory: `feedback_no_bot_first_person.md`)
- **No periods at the end of code comments.** Single-line comments are labels, not sentences. (memory: `feedback_no_periods_in_comments.md`)
- **Commit style**: no manual line wrapping in description, no AI co-author trailer (per global CLAUDE.md).
- **Branch is `master`**, not `main`. (memory: `user_branch_preference.md`)
- **Ask before saving memory.** Don't auto-save feedback. (memory: `feedback_ask_before_saving_memory.md`)
- **Ask before architectural decisions.** Surface structural questions instead of assuming. (memory: `feedback_ask_on_architecture.md`)

---

## How to resume after `/clear`

1. **Read this file.** Project layout + state in one place.
2. Memory files at `/home/mnoya/.claude/projects/-home-mnoya-Projects-Personal-DischordLeaderboard/memory/` auto-load — they capture preferences and conventions.
3. **Bring the stack up** if not already running:
   ```bash
   # Postgres
   docker start dischord-pg

   # Bot
   .venv/bin/python -u -m bot.main
   ```
4. **Refresh current data** (cache hit, no 17L call):
   ```bash
   .venv/bin/python -m bot.scripts.refresh_stats --cache
   ```
5. **After any slash-command code change**, DM the bot `!sync`.

---

## Open shape questions for the frontend slice (when we get there)

- Single-page or multi-page? (Spec says single page with set selector dropdown.)
- Read directly from Supabase via `supabase-js` (anon key + RLS) or proxy through a thin API?
- Where does the leaderboard URL live? Shared URL across sets, or `?set=SOS` query param?
- Per-format filter tabs (Premier / Trad / Sealed / Quick) — UI pattern?
- Mobile-first? (Spec says yes — community checks from phones.)

These can be sorted at the start of the frontend slice; flagging here so they don't get forgotten.
