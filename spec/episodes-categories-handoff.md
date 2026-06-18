# Episodes feed — categories, playback & URLs — handoff

Status as of this session. The Episodes page got a large overhaul: categorization moved entirely to the backend, in-place media playback, source-link affordances, search/sort tweaks, path-based category URLs, and — latest — a persistent left **Library sidebar** that replaces the horizontal category pills. **All changes are uncommitted** — bot changes in the working tree, frontend on `dev`. Local DB is recategorized and verified end-to-end; **prod is NOT backfilled yet** (see Rollout).

## The architecture decision (most important thing)

Episode **category is owned by the bot and stored in `episodes.category`** (exposed via the `public_episodes` view). The frontend just reads `row.category` and displays it — there is no client-side category guessing. An earlier iteration shipped a 769-entry LLM map + regex inference *in the browser bundle* that overrode the DB; that was removed. If you ever see "the frontend is computing categories", that's a regression.

## Taxonomy (8 categories)

`Set Review · Draft · Sealed · Rankings · Metagame · Coaching · Guest · Evergreen`. The list lives in two places that MUST stay in sync: `EPISODE_CATEGORIES` (frontend `frontend/src/data/episodes.ts`) and `CATEGORIES` (bot `bot/services/media_sync.py`). Definitions: Set Review = card-by-card/overview of a set's cards (incl. folded "First Impressions"); Draft = set-specific draft playthroughs/guides; Sealed = sealed/prerelease; Rankings = Top-N/tier lists/best-worst-of-year; Metagame = format state/updates/tournament reports; Coaching = the Chord_O_Coaching / "I coach X" series; Guest = interviews/conversations with a named guest (not host Alex / co-host Marc Anderson); Evergreen = timeless skill lessons + everything else (news, Q&A, retros).

## How a category is computed — `bot/services/media_sync.py::classify_category(playlists, title, kind, guid)`

Priority order (first hit wins):
1. **`_category_from_title_overrides`** (`_TITLE_OVERRIDES`) — hard manual rules that beat everything, including the seed. Currently just `first impressions? → Set Review`. This is where to force a title pattern.
2. **`_CATEGORY_SEED`** — `bot/services/episode_category_seed.json`, a guid→category map from a one-time LLM classification of the 769-episode back catalog. Consulted before the rules so a resync **reproduces** the curated labels instead of clobbering them back to rule output.
3. **`_category_from_playlists`** — Alex's YouTube playlists (the best human signal): `set review`, `coaching`/`draft class`, `sealed`, `top 10`/`tier list`/`ranking` → Rankings, `draft`, `evergreen`/`mini level`.
4. **`_category_from_title`** — regex rules (`_TITLE_CATEGORY_RULES`) + a top-N→Rankings catch (`_TOP_LIST`, excluding tournament-rank context and skill listicles like "Top 5 ways/tips").
5. **`_default_category`** — video→Draft, podcast→Evergreen.

Two ways to write the result to the DB:
- **Backfill (no feed fetch):** `DATABASE_URL=... python -m bot.scripts.recategorize_episodes` — re-runs `classify_category` over existing rows. Use after editing the seed or rules.
- **Full sync:** owner `!sync-media`, or `python -m bot.scripts.sync_media` — re-fetches Libsyn + YouTube and upserts. **Media sync is manual, not scheduled** — nothing auto-clobbers a backfill.

Categorization is a heuristic judgment call, intentionally NOT unit-tested — verify by eyeballing `recategorize_episodes` output / the DB, not by asserting title→category pairs (those just freeze a vibe-categorization that breaks on every taxonomy tweak).

## Frontend

- `frontend/src/data/episodes.ts::categoryFor(title, rawCategory)` — returns the DB category if it's a known value, else falls back to `inferCategory(title)` (the fallback only matters for live RSS/YouTube overlay items not yet synced into the DB). `adaptDbEpisode` uses it.
- `CategoryTag.tsx` — solid color chip per category. Palette added `blue`/`purple`/`orange` to `tailwind.config.ts` (Sealed=blue, Rankings=purple, Guest=orange; Set Review=teal, Draft=red, Metagame=gold, Coaching=green, Evergreen=border2). Still used on the cards; the sidebar rail is deliberately monochrome (see Layout).
- **Layout — Library sidebar** (`CategoryRail` + `RailRow`, both local to `EpisodesPage.tsx`). Replaces the old horizontal `FilterPill` row. A persistent left rail (244px, sticky, full-height surface + divider) lists All · Evergreen · the six others · a rule · Shorts, in a monochrome "green-spine" style: neutral rows, active row = solid green left spine + green label/count, hover fades the spine in. Row counts react to the active set + search scope (not category), so they never disagree with the grid (same logic as the old pills). The top bar (mobile `CATEGORIES` button + SET dropdown + search + sort + Listen-on) is `sticky top-0`; the page keeps **normal window scroll** (not an inner-scroll dashboard) so the existing infinite-scroll `IntersectionObserver` and `GoToTopButton` are unchanged. On `<lg` the rail collapses to a left **slide-in drawer** opened by the `CATEGORIES` button; picking a row closes it. The rail is wired to the existing URL navigation (`setCategory`/`showShorts`/`activeCategory`/`shortsView`) — path routing below is untouched. We evaluated several rail styles (color-keyed, solid tiles, count-forward, stacked spine, plus monochrome variants) on a throwaway `/episodes-lab/styles` page; the green-spine monochrome won. That scaffolding (`EpisodesLabPage`, `EpisodesLabStylesPage`, `/episodes-lab*` routes) has been **removed**.

## URLs / SEO

- **Path-based, lowercase, hyphenated** category routes (best for indexing — distinct canonical pages, no case-duplication): `/episodes/set-review`, `/episodes/sealed`, …, `/episodes/shorts`, and `/episodes` = All.
- `categorySlug()` / `categoryFromSlug()` in `episodes.ts`; route `/episodes/:categorySlug` in `App.tsx`; the page reads the slug via `useParams` and navigates via `useNavigate` (set filter / sort / search stay as query/state and are preserved across category nav).
- **Canonicalization:** a redirect effect rewrites legacy `?category=`/`?type=shorts` links to the path form, and an unknown slug bounces to `/episodes`.
- **Titles:** `DocumentTitle` (in-app tab title on SPA nav) mirrors `functions/_middleware.ts` (crawler/unfurl titles). The episodes section currently returns a generic title — per-category titles/descriptions are a TODO.

## Other episode features added this session (new, uncommitted)

- **In-place playback** — `PlayableThumbnail.tsx`: clicking a thumbnail plays inline. Video → YouTube iframe; podcast-only → custom `PodcastAudioPlayer.tsx` (themed scrubber `.audio-scrubber` in `styles.css`, play/pause via `Icons`, animated `Equalizer`, click-anywhere toggle). `PlayBadge.tsx` for the hover affordance (Play vs Music icon).
- **`MediaSourceLinks.tsx`** — YouTube / podcast source icons beside the category tag, each a new-tab link.
- **Shorts** — redundant "SHORT" badge removed; shorts play in place.
- **Search** — matches title + set name/code only. Summaries are NOT searched (they're ~all promo boilerplate — "Alex's Coaching Email…" matched ~230 episodes and made "coach" return 579). Pill counts also follow the search.
- **Sort** — segmented control (Newest/Oldest), replacing the dropdown.

## Rollout (NOT done — needs your go-ahead)

1. **Commit the bot, then push `master`** so Railway deploys the new categorizer. This must land **before** the next `!sync-media`, otherwise that manual sync runs the old categorizer and clobbers categories. (Backend is committed separately from the reviewed frontend.)
2. **Backfill prod:** `DATABASE_URL=<prod, from .env.supabase SUPABASE_DB_URL> .venv/bin/python -m bot.scripts.recategorize_episodes`. Reproducible (a resync regenerates the same labels), so low-risk, but it is a prod write.
3. **Review + commit the frontend.**

## Local dev state (how to view it now)

- `frontend/.env.local` is set to `VITE_DATA_MODE=local` — the frontend reads the local docker DB through `python -m bot.scripts.local_supabase_proxy` (port `:3001`, needs the local `DATABASE_URL`). Local DB was already recategorized (228 rows changed; distribution matches the seed). Flip back to `VITE_DATA_MODE=prod` + restart Vite to view prod.
- Typecheck after edits: `cd frontend && npx tsc -b` (keep clean).

## Future notes / TODO

- **Prod backfill + bot deploy** (Rollout above) — the big remaining step.
- **Per-category `<title>` + meta description** in `DocumentTitle` and `functions/_middleware.ts` (e.g. "Sealed Episodes — Limited Level-Ups") for the category URLs to rank.
- **`sitemap.xml`** listing the category URLs.
- **Trim the Evergreen tail** — interviews now route to Guest; news/announcements ("Play Boosters", "Combat change"), listener Q&A, and show retros still sit in Evergreen. Decide whether they get their own bucket or stay.
- **Hand-correction mechanism** — corrections currently live as either `_TITLE_OVERRIDES` (rule) or the seed JSON (per-guid). If per-guid corrections grow a lot, consider a DB override table instead of the checked-in seed.
- Review `SHOW_FORMAT` blurbs (`data/site.ts`) and the new tag colors.

## File map

- `bot/services/media_sync.py` — `classify_category` + the override/seed/playlist/title layers.
- `bot/services/episode_category_seed.json` — the 769 guid→category seed.
- `bot/scripts/recategorize_episodes.py` — in-place backfill.
- `frontend/src/data/episodes.ts` — `EPISODE_CATEGORIES`, `categorySlug`/`categoryFromSlug`, `categoryFor`/`inferCategory`, `adaptDbEpisode`.
- `frontend/src/pages/EpisodesPage.tsx` — page, path routing, legacy redirect, **Library sidebar (`CategoryRail`/`RailRow`) + mobile drawer**, search/sort.
- `frontend/src/components/` — `CategoryTag`, `PlayableThumbnail`, `PodcastAudioPlayer`, `PlayBadge`, `MediaSourceLinks`, `ShortCard`, `EpisodeCard`.
- `frontend/src/App.tsx` — `/episodes/:categorySlug` route + `DocumentTitle`. The `/episodes-lab*` prototype routes were removed.
- `functions/_middleware.ts` — server-side titles/descriptions.

### Adjacent shared changes (in the tree this session, used beyond Episodes)

- `frontend/src/lib/toggle-styles.ts` — added `FILTER_ACTIVE`/`FILTER_INACTIVE` (solid-green selected look) alongside the existing subtle `TOGGLE_*`. The sidebar rail and the sort control use the solid variant; `TOGGLE_*` stays for the SET dropdown trigger and the archetype color chips. One shared constant so the selected look is consistent.
- `frontend/src/components/FilterDropdown.tsx` — added an `align?: "left" | "right"` prop (right anchors the open panel so a right-edge trigger doesn't overflow the viewport).
- `frontend/src/components/SetFilterDropdown.tsx` — NEW shared wrapper around `FilterDropdown` (glyph + code trigger, glyph + name list, searchable). Introduced to give the **Leaderboard mobile** set switcher the Episodes-style searchable dropdown; not yet used on the Episodes page itself (which still has its own count-bearing SET dropdown).
- `frontend/src/pages/LeaderboardPage.tsx` — mobile set switcher swapped from `SetSwitcherMobile` to `SetFilterDropdown` (`align="right"`); desktop chamfered chip row untouched.

> Co-editing hazard: `EpisodesPage.tsx` was being edited in an IDE while these changes landed, and an editor save once reverted the sidebar transplant. If the layout looks like the old pills, the on-disk file was overwritten by a stale editor buffer — reload the file from disk before re-editing.
