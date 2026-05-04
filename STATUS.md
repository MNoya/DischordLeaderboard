# DischordLeaderboard — Status Snapshot

Updated 2026-05-03. Backend + Discord bot are functional end-to-end against live 17lands data, polished through a long UX iteration on the `leaderboard-tweaks` branch. Supabase project provisioned. Railway not deployed. Frontend not started.

---

## What this project is

A Discord bot + (planned) public website for an MTGA community leaderboard called **LLU**. Players link their 17lands profile through Discord; the bot pulls their draft data, computes a score using a custom formula, and ranks them within the current Magic set. Multi-server-capable (single shared leaderboard across all guilds the bot is invited to). Fully automated — no manual score submission.

---

## Tech stack

| Layer | Tech | Status |
|---|---|---|
| Discord bot | `discord.py>=2.3` | Running locally |
| Database | Postgres (local Docker dev, Supabase prod) | `dischord-pg` on `:5433` (dev); Supabase project `yrecdosksgigpceholjl` (prod, sets-only seeded) |
| ORM / migrations | SQLAlchemy 2.0 + Alembic, `DateTime(timezone=True)` everywhere | One initial migration `e8c3a1b2f0d4_initial_schema` (rewritten in-place several times — pre-launch) |
| Config | Code constants in `bot/sets.py` for the active set; `pydantic-settings` for the rest | `bot/config.py` |
| 17lands client | `requests` + custom rate limiter + JSON file cache | `bot/services/seventeenlands.py` |
| Scoring | Custom formula (legacy ECL formula adapted) | `bot/scoring.py` |
| Tests | `pytest` + `testcontainers[postgres]` + `responses` | 115 passing |
| CI | GitHub Actions | `.github/workflows/ci.yml` (master branch) |
| Frontend | React + Vite | NOT STARTED |
| Deployment | Railway (bot), Netlify (frontend), Supabase | Supabase ✅, Railway ❌, Netlify ❌ |

---

## Repo layout

```
.
├── alembic/                       # DB migrations
│   ├── env.py                     # reads DATABASE_URL via bot.config.settings
│   └── versions/e8c3a1b2f0d4_initial_schema.py
├── alembic.ini
├── bot/
│   ├── config.py                  # pydantic-settings: DATABASE_URL, DISCORD_*, public_site_url
│   ├── sets.py                    # SetSeed dataclass, ALL_SETS tuple, ACTIVE_SET_CODE constant — single source of truth
│   ├── database.py                # SessionLocal + run_migrations()
│   ├── models.py                  # Player, MagicSet, PlayerStats, PlayerSetScore, DraftEvent, LeaderboardMessage
│   ├── scoring.py                 # QueueGroup, DEFAULT_QUEUE_GROUPS, compute_score, compute_score_breakdown
│   ├── audit.py                   # Append-only JSONL event log → logs/events.jsonl
│   ├── main.py                    # Bot entry point; tree.error handler with owner-DM crash report; !sync, !refresh prefix commands
│   ├── assets/
│   │   └── signup_event_history.png  # Walkthrough screenshot attached to /join DM
│   ├── commands/
│   │   ├── signup.py              # /join (slash) — DM walkthrough, per-user lock, post-join leaderboard+stats preview
│   │   ├── signout.py             # /retire (slash) — replies via DM
│   │   ├── update_profile.py      # /relink (slash)
│   │   ├── delete_account.py      # /exile (slash, DM-only) — soft 'remove from leaderboard' wording
│   │   ├── leaderboard.py         # /leaderboard (slash) + persistent Join+Stats view; tracked-message editing
│   │   ├── stats.py               # /stats (slash)
│   │   └── help.py                # /help (slash)
│   ├── services/
│   │   ├── seventeenlands.py      # SeventeenLandsClient + MinIntervalLimiter + aggregate_for_set + extract_events_for_set
│   │   └── refresh.py             # refresh_player (writes PlayerStats AND DraftEvent), refresh_active_players, recompute_player_set_score
│   ├── scripts/
│   │   ├── seed_sets.py              # seeds magic_sets from bot/sets.py ALL_SETS — idempotent
│   │   ├── seed_local_players.py     # seeds Players from legacy/user_ids.py — local-dev only
│   │   ├── refresh_stats.py          # CLI: pull 17lands + write PlayerStats + DraftEvents + recompute scores
│   │   └── recompute_scores.py       # CLI: recompute PlayerSetScore from existing PlayerStats (no 17L fetch)
│   └── tests/
│       ├── conftest.py            # Postgres testcontainer fixture
│       ├── test_seventeenlands.py
│       ├── test_refresh.py
│       ├── test_scoring.py
│       ├── test_signup.py
│       ├── test_signout.py
│       ├── test_update_profile.py
│       ├── test_delete_account.py
│       └── test_leaderboard.py
├── legacy/                        # Original spreadsheet-era code (reference; aggregator + scoring formula)
│   ├── aggregator.py
│   ├── leaderboard.py
│   ├── main.py
│   └── user_ids.py                # PLAYERS list (gitignored)
├── cache/17lands/                 # Per-token JSON cache for dev (gitignored)
├── logs/                          # bot.log + events.jsonl (gitignored)
├── .claude/skills/new-set/        # /new-set skill — automates set rotation
├── .github/workflows/ci.yml       # alembic upgrade head + alembic check + pytest on master
├── .env                           # DATABASE_URL, DISCORD_BOT_TOKEN, DISCORD_GUILD_ID (gitignored)
├── .env.example                   # documented env vars
├── railway.json                   # Railway deployment config (start cmd, restart policy)
├── .python-version                # 3.12
├── requirements.txt               # prod-only deps (Nixpacks-detected)
├── requirements-dev.txt           # adds pytest, testcontainers, responses
├── web/                           # Static coming-soon site (Netlify)
│   └── index.html
├── mtga-leaderboard-spec.md       # Original project spec
├── pod-draft-spec.md              # Design for pod-draft tracking feature (not yet built)
└── STATUS.md                      # This file
```

---

## Slash commands (Discord)

All commands work in both server channels and DMs with the bot, **except** `/exile` which is DM-only.

| Command | Purpose | Visibility |
|---|---|---|
| `/leaderboard` | Show current set leaderboard. In a guild: posts publicly to the channel + ephemeral stats followup. In DM: posts to DM + stats followup. | Server + DM |
| `/stats [player]` | Per-player formula breakdown by queue group | Server + DM |
| `/join` | Sign up — DM walkthrough flow with 17lands token. Post-success DM also includes the leaderboard + the player's own stats embed. Per-user lock prevents duplicate concurrent flows. | Server + DM |
| `/retire` | Pause participation. Replies via DM so the user is in the right channel for `/exile` if they want it. | Server + DM |
| `/relink` | Update 17lands token | Server + DM |
| `/help` | List commands | Server + DM |
| `/exile` | Permanently remove yourself from the leaderboard (DM-only) | DM only |

**`/leaderboard` Join + Stats button view** is persistent (registered via `bot.add_view(LeaderboardView())` at startup) so buttons keep working across bot restarts. Join button auto-routes to `/stats` if the clicker is already signed up (treats Join-button click as "show me my stats" in that case).

**Owner-only prefix commands** (text, in DM with the bot):
- `!sync` — push slash command changes to Discord. Run after editing any command's name/description/options.
- `!refresh [SET_CODE]` — pull stats from 17lands for active players, DM invalidated tokens, edit every tracked leaderboard message in place with new data.

`!refresh` defaults to `ACTIVE_SET_CODE` from `bot/sets.py`. Pass a code to refresh historical sets.

---

## Data model

```
players (id, discord_id?, discord_username?, display_name, seventeenlands_token, ...)
sets (id, code, name, start_date, end_date)
player_stats (id, player_id, set_id, format, expansion, events, wins, losses, games_played, trophies, last_fetched_at)
  UNIQUE (player_id, set_id, format, expansion)
player_set_scores (id, player_id, set_id, score, trophies, last_calculated_at)
  UNIQUE (player_id, set_id)
draft_events (id, player_id, set_id, seventeenlands_event_id, format, expansion, wins, losses, is_trophy,
              colors, start_rank, end_rank, started_at, finished_at, fetched_at)
  UNIQUE (player_id, seventeenlands_event_id)
leaderboard_messages (id, channel_id, set_id, message_id, last_rendered_at)
  UNIQUE (channel_id, set_id)
```

- **All `DateTime` columns are `DateTime(timezone=True)` (= TIMESTAMPTZ)** — fixes the foot-gun where naive UTC datetimes were misinterpreted by discord.py as local time, shifting timestamps by the host's UTC offset.
- `players.discord_id` is **nullable** so seeded legacy players can exist before linking via `/join`.
- `player_stats` is per-(player, set, format, expansion) — Alchemy variants like `Y26ECL` get their own row but bucket under `ECL` for scoring.
- `player_set_scores` is the pre-computed total written by `refresh_player`. `last_calculated_at` is force-bumped every refresh (not just when score changes) so the "Last updated" footer reflects refresh time, not score-change time.
- `draft_events` captures one row per individual 17lands draft for future features (favorite deck by colors, trophy streaks, mythic-rank leaderboards, ALCQ tracking). 17lands' case-encoded color string (`WBg` = WB main + green splash) is preserved verbatim in `colors`.
- `leaderboard_messages` tracks the bot's posted leaderboard per (channel, set) so `/leaderboard` can delete-and-repost (instead of duplicating) and `!refresh` can edit in place. Stale rows (message deleted in Discord) get pruned on next edit attempt.
- No `is_current` flag on sets — current set is `ACTIVE_SET_CODE` in `bot/sets.py` (was an env var, now a code constant).

---

## Set rotation

`bot/sets.py` is the single source of truth for set metadata + which one is currently active:

```python
ACTIVE_SET_CODE = "SOS"

ALL_SETS = (
    SetSeed("FIN", "Final Fantasy",              date(2025,  6, 10), date(2025, 11, 17)),
    SetSeed("TLA", "Avatar: The Last Airbender", date(2025, 11, 18), date(2026,  1, 19)),
    SetSeed("ECL", "Lorwyn Eclipsed",            date(2026,  1, 20), date(2026,  4, 20)),
    SetSeed("SOS", "Secrets of Strixhaven",      date(2026,  4, 21), date(2026,  6, 22)),
)
```

Rotating to a new set:
1. Run **`/new-set MSH`** (Claude Code skill at `.claude/skills/new-set/SKILL.md`):
   - Web-looks-up the new set's official name + Arena release date
   - Edits `bot/sets.py`: appends new entry, closes prior set's `end_date`, bumps `ACTIVE_SET_CODE`
   - Runs `seed_sets` and `refresh_stats --set-code <CODE>` against `DATABASE_URL`
   - Commits the change locally (does not push)
2. Push to master → Railway redeploys → bot picks up the new active set.

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

**Local Postgres**: Docker container `dischord-pg` on host port 5433. DB `dischord`, user `postgres`, password `devpw`. Wipe-and-reseed sequence:
```bash
docker exec dischord-pg psql -U postgres -d dischord -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/alembic upgrade head
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/python -m bot.scripts.seed_sets
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/python -m bot.scripts.seed_local_players
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/python -m bot.scripts.refresh_stats --cache
```

**Supabase (prod)**: project `yrecdosksgigpceholjl`, region `us-east-2`. Connection via Transaction Pooler at `aws-1-us-east-2.pooler.supabase.com:6543`. **Schema applied early in the session, but the initial migration was rewritten twice afterward** (added `draft_events`, then switched to TIMESTAMPTZ). Before deploying, Supabase needs:
```sql
-- in Supabase SQL Editor
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
```
Then locally:
```bash
DATABASE_URL='<pooler-url-with-encoded-password>' .venv/bin/alembic upgrade head
DATABASE_URL='<pooler-url-with-encoded-password>' .venv/bin/python -m bot.scripts.seed_sets
```
(No player seeding for prod — players self-join via `/join`.)

**Bot**: started locally with `.venv/bin/python -u -m bot.main`. Logs to `logs/bot.log` and console.

**17lands cache**: 11 player JSONs at `cache/17lands/<token>__2026-04-21.json`. Re-fetch live with `python -m bot.scripts.refresh_stats` (no `--cache`).

**Branch state**: First deploy shipped. `leaderboard-tweaks` (PR #1) and `predeploy-prep` (PR #2) are merged. Subsequent small commits go directly to `master` per the solo-repo workflow preference (see memory `feedback_solo_repo_direct_master.md`).

**Bot identity**: Discord Application ID `1466076574372724819` (decode-able from the bot token but worth recording). User-facing display name: `DisChord Bot#1519`.

**Production guild**: LLU community server, guild ID `775371722065051658`. Bot was invited via OAuth URL with `bot + applications.commands` scopes and permissions integer `117760` (View Channels + Send Messages + Embed Links + Attach Files + Read Message History). Bot's role at the guild level has those perms; **per-channel permission overrides can still block edits** — e.g. a restricted channel where the bot can post the original `/leaderboard` reply via interaction-token auth but later 403s on `msg.edit` from `broadcast_current_set_update`. Workaround: grant the bot explicit channel access, or use a less restricted channel.

---

## Outstanding tasks

| # | Task | Status | Notes |
|---|---|---|---|
| A | Push `leaderboard-tweaks` and merge | done | Squashed and merged via PR #1 |
| B | Reset Supabase schema + re-seed sets | done | Schema dropped + migrated to head `e8c3a1b2f0d4`; 4 sets seeded (FIN, TLA, ECL, SOS). Pooler URL stashed in gitignored `.env.supabase` for the Railway step. |
| C | Railway deployment | done | Deployed from GitHub `master`. Env vars set: `DATABASE_URL` (Supabase pooler), `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID=775371722065051658` (LLU production guild). Nixpacks build + `railway.json` start command. Bot logged in as `DisChord Bot#1519`, smoke-tested with `/leaderboard` and `/join` in LLU. |
| D | Coming-soon placeholder → Netlify | done | Live at https://dischordboard.netlify.app/ from `web/index.html` on `master`. `bot.config.public_site_url` default updated to match. |
| E | Build React + Vite frontend | parked | Real frontend deferred until after first deploy. Per-player URL pattern `/player/{player_id}` reserved (`_player_url` helper in `bot/commands/leaderboard.py` is unused for now). |
| F | Pod-draft tracking feature | designed, not built | See `pod-draft-spec.md` |

**Optional micro-cleanup** (no task tracked):
- Rank movement arrows (▲▼) inspired by scoreboards.dev — needs a previous-rank snapshot table.
- Delete `logs/bot.log` from `.gitignore` since it's now under `logs/` blanket gitignore (low priority — `.gitignore` is fine as is).

**Deferred / parked decisions**:
- Per-set scoring config (currently `DEFAULT_QUEUE_GROUPS` is global; per-set future-proofing not built).
- 17lands OAuth flow (would replace the URL-paste signup; ideal but requires 17lands building an OAuth provider).
- Two-deployment dev/prod separation (current plan: dev bot runs locally, prod bot runs on Railway — same repo, different env).

---

## Conventions / things to keep doing

- **Tests target logic, not framework behavior.** No tests for "does Postgres work" or "does Alembic apply migrations." Tests focus on aggregator / scoring / signup-flow branches / etc. (memory: `feedback_test_logic_not_integrity.md`)
- **Bot user-facing strings avoid first-person.** No "I sent you a DM" — use "Check your DMs" instead. (memory: `feedback_no_bot_first_person.md`)
- **No "sign up" in user copy** — use "join" / "joined" / "on the leaderboard" for consistency with `/join`. Internal Python identifiers (`process_signup`, `SignupKind`, audit event names) stay as-is.
- **`ephemeral=True` is gated to guild context** — every callsite uses `ephemeral=(interaction.guild is not None)` so DMs don't get the "only you can see this message" auto-expire badge.
- **Use the short set code (`SOS`) in user-visible strings** like the leaderboard title and `/stats` footer — full set names ("Secrets of Strixhaven") are too long for those slots.
- **No periods at the end of code comments.** Single-line comments are labels, not sentences. (memory: `feedback_no_periods_in_comments.md`)
- **Commit style**: subjects start with uppercase, no manual line wrapping in description, no AI co-author trailer, no banned writing-style words like "surface" as a verb. (memories: `feedback_commit_subject_uppercase.md`, global CLAUDE.md, plus the no-banned-writing hook in `~/.claude/hooks/`)
- **Branch is `master`**, not `main`. (memory: `user_branch_preference.md`)
- **Ask before saving memory.** Don't auto-save feedback. (memory: `feedback_ask_before_saving_memory.md`)
- **Ask before architectural decisions.** Surface structural questions instead of assuming. (memory: `feedback_ask_on_architecture.md`)

---

## How to resume after `/clear`

1. **Read this file.** Project layout + state in one place.
2. Memory files at `/home/mnoya/.claude/projects/-home-mnoya-Projects-Personal-DischordLeaderboard/memory/` auto-load — they capture preferences and conventions.
3. **Bring the stack up** if not already running:
   ```bash
   docker start dischord-pg
   .venv/bin/python -u -m bot.main
   ```
4. **Refresh current data** (cache hit, no 17L call):
   ```bash
   .venv/bin/python -m bot.scripts.refresh_stats --cache
   ```
5. **After any slash-command schema change** (name, description, options), DM the bot `!sync`. Pure body changes don't need it.

---

## Open shape questions for the frontend slice (when we get there)

- Single-page or multi-page? (Spec says single page with set selector dropdown.)
- Read directly from Supabase via `supabase-js` (anon key + RLS) or proxy through a thin API?
- URL pattern: leaderboard root + `?set=SOS` query param? Player profile pages live at `/player/{player_id}` (helper `_player_url` reserved in `bot/commands/leaderboard.py`, not yet wired into row rendering — wire it up once the frontend ships).
- Per-format filter tabs (Premier / Trad / Sealed / Quick) — UI pattern?
- Mobile-first? (Spec says yes — community checks from phones.)
- "Favorite deck" / color-archetype features now possible via `draft_events` table (per-event color data captured).

These can be sorted at the start of the frontend slice; flagging here so they don't get forgotten.
