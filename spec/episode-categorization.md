# Episode categorization — spec & status

Self-contained reference for how episode **categories** (the colored tag / filter facet on `/episodes`) are decided. Scope is categorization only; in-place playback, source links, the Library sidebar, and the path-based category URLs live in `spec/episodes-categories-handoff.md`.

## TL;DR / where we stand

- Category is **owned by the bot and stored in `episodes.category`** (Postgres, surfaced via the `public_episodes` view). The frontend reads `row.category` and displays it — no client-side categorization. This was a deliberate move away from an earlier browser-side LLM map.
- The bot computes a category from a fixed **priority pipeline** (overrides → one-time LLM seed → YouTube playlists → title rules → default → a post-correction). It runs on media sync and via a standalone backfill script.
- **Local DB is fully recategorized and verified. PROD is NOT backfilled yet, and the bot is NOT deployed.** That's the main outstanding work (see Outstanding).
- Categorization is a **heuristic judgment call — intentionally not unit-tested.** Verify by eyeballing the backfill output or the review table, not by asserting title→category pairs.

## Taxonomy (8 categories)

`Set Review · Draft · Sealed · Rankings · Metagame · Coaching · Guest · Evergreen`

The list must stay in sync in two places: `CATEGORIES` in `bot/services/media_sync.py` and `EPISODE_CATEGORIES` in `frontend/src/data/episodes.ts`.

- **Set Review** — card-by-card / overview of a set's cards for a release (incl. the folded-in "First Impressions").
- **Draft** — actual draft VODs (draft-alongs). **YouTube-video-only by rule** — a podcast episode is never Draft.
- **Sealed** — sealed / prerelease content.
- **Rankings** — Top-N lists, tier lists, best/worst-of-year, "props and slops".
- **Metagame** — format state/health, format updates, draft guides/primers, format-specific tips & win-rate content, tournament/PT recaps. The catch-all for "about a current format but not a draft VOD".
- **Coaching** — the Chord_O_Coaching / "draft class" / "I coach X" series.
- **Guest** — interviews/conversations built around a named guest (not host Alex / not regular co-host Marc Anderson).
- **Evergreen** — timeless skill lessons + residual (news/announcements, listener Q&A, retrospectives).

**Shorts is NOT a category** — it's a separate, orthogonal axis. `Episode.isShort` (`isShortMedia(kind, durationSeconds, title)` in `episodes.ts`: a vertical YouTube clip ≤90s, or ≤3min carrying the `#draft #mtg` hashtag run) is independent of `category`. A short still carries one of the 8 categories; the Shorts pill/view filters on the `isShort` boolean, not on `category`. So the sidebar's `Shorts` row is a length filter that lives alongside the category rows, not a 9th category.

## Classification pipeline — `classify_category(playlists, title, kind, guid)`

First match wins, in this order:

1. **Title overrides** (`_TITLE_OVERRIDES`) — hard rules that beat everything incl. the seed. Currently: `first impressions → Set Review`; `draft primer | draft guide | win rate | tips for success → Metagame`.
2. **Seed** (`bot/services/episode_category_seed.json`, loaded as `_SEED_CATEGORY`/`_SEED_SET` in `media_sync`) — per-guid map: a one-time LLM classification of the 769-episode back catalog **plus committed hand-corrections**. Consulted before the rules so a resync reproduces it. Each value is a category string, or `{"category"?, "set"?}` when an episode also needs a manual `set` the title can't yield (e.g. a guest episode, a generically-titled season entry). The `set` half is applied by `resolve_episode_set` (see Set resolution).
3. **Playlists** (`_category_from_playlists`) — the channel's YouTube playlists (Alex's own curation; the strongest signal where present): `set review`, `coaching`/`draft class`, `sealed`, `top 10`/`tier list`/`ranking`→Rankings, `draft`, `evergreen`/`mini level`.
4. **Title rules** (`_category_from_title`, `_TITLE_CATEGORY_RULES`) — regexes for Coaching/Guest/Rankings/Set Review/Sealed/Metagame/Draft, plus a `Top N …`→Rankings catch (excluding tournament-rank context and skill listicles like "Top 5 tips/ways").
5. **Default** (`_default_category`) — video→Draft, podcast→Evergreen.
6. **Post-correction** — if the result is `Draft` and `kind == "episode"`, it becomes `Metagame`. Draft is YouTube-video-only; a podcast episode is format talk, never a draft-along.

Note the asymmetry: overrides run *before* the seed (so they can fix seed mistakes by title), the EP→Metagame correction runs *after* (so it catches seed-assigned Drafts on podcast rows too).

## Where it lives

- `bot/services/media_sync.py` — `classify_category` + all the layers; `CATEGORIES`. Written to `episodes.category` on every sync (`_upsert`).
- `bot/services/episode_category_seed.json` — the 769 guid→category seed.
- `bot/scripts/recategorize_episodes.py` — re-runs `classify_category` **and** `resolve_set` over existing rows in place (no feed fetch), updating `category` + `set_code`/`set_name`/`set_released_at`. The backfill tool.
- `bot/scripts/sync_media.py` / owner `!sync-media` — full re-fetch of Libsyn + YouTube, then upsert. **Sync is manual, not scheduled** — nothing auto-clobbers a backfill.
- `bot/scripts/episode_review_table.py` — emits a markdown table (`episode-categories-review.md`) of date/kind/set/category/title/playlists exactly as a sync would store, for eyeball review.
- `frontend/src/data/episodes.ts` — `categoryFor(title, rawCategory)` returns the DB category if valid, else `inferCategory(title)` (a frontend regex fallback, only hit by un-synced live RSS/YouTube overlay items). `adaptDbEpisode` uses it.

## Applying & verifying

```
# backfill a DB in place (local)
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord .venv/bin/python -m bot.scripts.recategorize_episodes

# review table
DATABASE_URL=... .venv/bin/python -m bot.scripts.episode_review_table   # -> episode-categories-review.md
```

The recategorize script prints the per-category distribution and a "N changed" count — that's the verification surface.

## Current state (local DB, latest backfill)

`Draft 257 · Set Review 169 · Metagame 110 · Evergreen 98 · Guest 45 · Sealed 38 · Coaching 34 · Rankings 18` (= 769). Prod still holds the OLD pre-overhaul categories until rolled out.

## Outstanding / what needs to be addressed

1. **Prod rollout (the big one).** Commit the bot and push `master` so Railway deploys the new categorizer — this must land **before** the next `!sync-media`, or that manual sync runs the old code and clobbers categories. Then backfill prod: `DATABASE_URL=<prod, from .env.supabase SUPABASE_DB_URL> .venv/bin/python -m bot.scripts.recategorize_episodes`. Reproducible, but it's a prod write.
2. **Seed drift.** The seed is a frozen LLM snapshot. As the taxonomy/rules evolve, seed values can be "wrong" and only get fixed where a title override or the EP→Metagame correction happens to catch them. Decide a long-term story: keep layering overrides, periodically regenerate the seed, or migrate per-episode corrections out of the seed (see #3).
3. **Hand-correction mechanism (decided).** Corrections live in two shapes: `_TITLE_OVERRIDES` (pattern rules, for whole classes like "draft guide → Metagame") and the **seed JSON** (per-guid, for one-offs — both category and `set`). We deliberately fold per-episode corrections into the committed seed rather than a separate overrides file, since the seed is versioned in git. Trade-off: the seed is no longer a pristine LLM baseline, so a future seed *regeneration* must preserve or re-apply the hand-edited entries (they're identifiable as the non-string `{category,set}` values + a handful of changed strings).
4. **New-episode quality.** Episodes not in the seed rely on playlists + title rules. There are **no Guest / Rankings / Sealed playlists** on the channel, so new episodes in those buckets depend entirely on title regex. Option: ask Alex to maintain playlists for them, or accept title-rule coverage and spot-fix.
5. **Evergreen tail.** Evergreen still mixes genuine skill lessons with news/announcements, listener Q&A, and retrospectives. Decide whether any of those graduate to their own bucket.
6. **Frontend fallback duplication.** `inferCategory` in `episodes.ts` is a small client-side regex mirror used only for un-synced live overlay items. It's a (minor) re-introduction of client-side guessing; consider whether live overlay items should instead show no category / "Evergreen" until the bot syncs them, and delete `inferCategory`.

## Known judgment rules baked in (so they aren't "fixed" by accident)

- A **podcast episode is never Draft** (→ Metagame). Draft = YouTube draft VODs only.
- **Draft Guide / Draft Primer / Limited Guide → Metagame** (a format guide, not a card review — overrides the "primer"→Set Review title rule).
- **Win-rate / "tips for success" / format-tips content → Metagame** (short-form format talk).
- **First Impressions → Set Review** (the "First Impressions" bucket was retired/folded).

Set resolution (sibling concern, also backfilled by `recategorize_episodes`): `media_sync.resolve_episode_set(guid, playlists, title, published)` applies the per-guid seed `set` first, then falls back to `media_sets.resolve_set(playlists, title, published)` (title → playlist → EVERGREEN). Two date/alias rules live in `resolve_set`: **"Strixhaven" from 2026 → SOS** (older stays STX, the 2021 set), and the `new capenna` alias resolves "New Capenna Draft Class" → SNC. Per-guid set overrides in the seed cover what neither can infer (e.g. "…with TBD" → THB, generically-titled "DRAFT CLASS #3/4/5" → NEO).
