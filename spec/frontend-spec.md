# DischordLeaderboard Frontend — Spec

Status: planning. No code yet. This document captures the agreed shape of the v1 web frontend so implementation proceeds against a fixed contract.

---

## Goals

A public web frontend for the LLU community leaderboard, fed by the existing Supabase database, designed from day one to slot under `limitedlevelups.com/leaderboard` if/when the broader community site launches.

Two views in v1:

1. **Leaderboard** — current set by default, with set / format / archetype filters and history of past sets.
2. **Player profile** — `/player/{slug}` showing per-set, per-format, per-archetype breakdowns plus draft history for one player.

Public read-only at launch. Discord OAuth slated as a follow-up so signed-in users see "highlight me" / personalized comparisons.

---

## Out of scope for v1

- Authentication of any kind (no Discord OAuth in v1)
- Editing data from the web — the bot stays the only writer
- Real-time updates — data refresh happens on page load, governed by TanStack Query stale-time
- Pod-draft tracking views (`pod-draft-spec.md`, separate phase)
- Rank movement arrows (▲▼) — needs a previous-rank snapshot table that doesn't exist yet
- Combined archetype × format leaderboards (e.g. "best UW Premier drafter") — archetype scope is across all formats in v1; per-format slice deferred

---

## Architecture decisions (locked)

| # | Decision |
|---|---|
| 1 | TS as the source of truth for UI shapes; fixtures and live data both target the same types |
| 2 | Presentational components: props in, JSX out, no fetch knowledge |
| 3 | Data hook layer (`useLeaderboard(setCode)`, `usePlayerProfile(slug)`, `useDraftEvents(slug)`, `useRecentTrophies(setCode)`) abstracts source |
| 4 | Adapter layer translates Supabase view rows (snake_case) into camelCase UI types |
| 5 | TanStack Query for caching, with per-set keys |
| 6 | Idle-time prefetch of non-active sets after first paint |
| 7 | Within-set format filter is a client-side reduction of cached rows; archetype filter switches data source to a per-archetype view |
| 8 | Hybrid URL: path = entity (`/sos`, `/player/{id}`), query = filters (`?format=Premier`) |
| 9 | No Redux. Zustand or React Context only if a real need appears |
| 10 | `supabase-js` direct from the browser, against curated public views (no service-role key in client) |
| 11 | Mobile-first; desktop shows wider layout / extra columns |
| 12 | Component library / styling stack deferred — picked once Claude Design output suggests one |
| 13 | Cloudflare Pages as deploy target; SPA with React Router |
| 14 | Vite `base = '/'`: the app serves from the domain root with the leaderboard as one section (`/leaderboard`) alongside `/tier-list`, `/episodes`, `/pods` |

---

## Data contract

The frontend reads exclusively from a small set of curated Postgres views in the `public` schema. Base tables stay locked down — no anon grants, RLS enabled. Tokens, internal IDs, and any sensitive fields never appear in any view.

### Views (to be created)

**`public_sets`** — set list with computed active flag.
```
code         text       -- 'SOS', 'ECL', ...
name         text       -- 'Secrets of Strixhaven'
start_date   date
end_date     date
is_active    boolean    -- computed: today BETWEEN start_date AND end_date
```

**`public_leaderboard`** — one row per (player, set) for players with at least one event in that set.
```
set_code            text
slug                text       -- URL handle, e.g. 'chonce', 'neo-marc'; used for /player/{slug} routing
display_name        text
avatar_url          text       -- nullable; computed in the view from discord_id + avatar_hash
rank                int
score               numeric
trophies            int
events              int
wins                int
losses              int
last_calculated_at  timestamptz
```

The internal `players.id` UUID stays the primary key inside the DB (used for foreign keys and joins) but is **never exposed** in any public view. Frontend identifies players exclusively by `slug`. See *Slug generation* below.

`avatar_url` is computed inside the view so `discord_id` never leaks to the browser:

```sql
CASE WHEN p.avatar_hash IS NOT NULL
  THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=64'
  ELSE NULL
END AS avatar_url
```

**`public_player_format_breakdown`** — one row per (player, set, format-group). Used by player-profile pages.
```
set_code             text
slug                 text
format_label         text       -- 'Premier', 'Sealed', 'Quick', ...
events               int
wins                 int
losses               int
trophies             int
score_contribution   numeric
```

**`public_player_draft_events`** — per-event row, used for archetype/colour analysis and draft history on the profile page. Loaded lazily per-player, not eagerly.
```
slug          text
set_code      text
event_id      text
format        text
expansion     text
wins          int
losses        int
is_trophy     boolean
colors        text       -- e.g. 'WBg' (case-encoded archetype, preserved verbatim from 17lands)
started_at    timestamptz
finished_at   timestamptz
```

**`public_recent_trophies`** — recent trophy events across all players for a given set. Backs the "RECENT TROPHIES" sidebar card on the leaderboard. Sorted `finished_at DESC` server-side; consumers paginate by limit only.
```
set_code      text
slug          text
display_name  text
avatar_url    text       -- nullable; same compute rule as public_leaderboard
format        text       -- raw 17lands format (e.g. 'PremierDraft')
colors        text       -- raw 17lands color string preserved verbatim
wins          int
losses        int
finished_at   timestamptz
```
Implementation note: a thin view over `draft_events` filtered to `is_trophy = true`, joined to `players` for the display side fields. No precomputed table needed — at SOS-scale volumes (~1.5k events / set) the on-demand query is cheap.

**`public_archetype_leaderboard`** — one row per (player, set, archetype), for cells where the player has at least one event. Backs the per-archetype leaderboard ("best UW drafter for SOS"). See the *Per-archetype leaderboard* section below for the formula and qualifying rules.
```
set_code            text
archetype           text       -- 'UW', 'BG', 'WUBR', 'WUBRG', '' (colorless), ...; uppercase main colors only, sorted WUBRG
slug                text
display_name        text
avatar_url          text
rank                int        -- within (set, archetype), score desc, winrate desc tiebreaker
score               numeric    -- subset-replay score: compute_score run on this player's events restricted to this archetype, summed across formats
trophies            int
events              int
wins                int
losses              int
last_calculated_at  timestamptz
```

### TS types (mirror the views)

`frontend/src/types/leaderboard.ts`

```ts
export interface SetSummary {
  code: string;
  name: string;
  startDate: string;     // ISO date
  endDate: string;
  isActive: boolean;
}

export interface LeaderboardRow {
  setCode: string;
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  rank: number;
  score: number;
  trophies: number;
  events: number;
  wins: number;
  losses: number;
  lastCalculatedAt: string;
}

export interface PlayerFormatBreakdown {
  setCode: string;
  slug: string;
  formatLabel: string;
  events: number;
  wins: number;
  losses: number;
  trophies: number;
  scoreContribution: number;
}

export interface PlayerDraftEvent {
  slug: string;
  setCode: string;
  eventId: string;
  format: string;
  expansion: string;
  wins: number;
  losses: number;
  isTrophy: boolean;
  colors: string;
  startedAt: string;
  finishedAt: string;
}

export interface ArchetypeLeaderboardRow {
  setCode: string;
  archetype: string;        // 'UW', 'WUBR', '' for colorless, etc
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  rank: number;
  score: number;
  trophies: number;
  events: number;
  wins: number;
  losses: number;
  lastCalculatedAt: string;
}

export interface RecentTrophy {
  setCode: string;
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  format: string;           // raw 17lands format ('PremierDraft', 'TradDraft', ...)
  colors: string;           // raw 17lands color string ('WBg', 'UR', ...)
  wins: number;
  losses: number;
  finishedAt: string;
}
```

The adapter (`frontend/src/data/adapter.ts`) converts snake_case rows from Supabase into these camelCase types. Components only see the camelCase shape. Fixtures match it directly — no adapter needed for fixtures.

### RLS / grants

```sql
-- All base tables: RLS on, no anon grants.
ALTER TABLE players              ENABLE ROW LEVEL SECURITY;
ALTER TABLE sets                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_stats         ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_set_scores    ENABLE ROW LEVEL SECURITY;
ALTER TABLE draft_events         ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaderboard_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE alembic_version      ENABLE ROW LEVEL SECURITY;

-- Anon role gets SELECT only on the curated views.
GRANT SELECT ON public_sets                     TO anon;
GRANT SELECT ON public_leaderboard              TO anon;
GRANT SELECT ON public_player_format_breakdown  TO anon;
GRANT SELECT ON public_player_draft_events      TO anon;
GRANT SELECT ON public_recent_trophies          TO anon;
GRANT SELECT ON public_archetype_leaderboard    TO anon;
```

The bot keeps writing through the `postgres` superuser, which bypasses RLS.

---

## Slug generation

`players.slug` is a URL-safe handle derived from `display_name`, frozen at first sight. New column on `players` (`text not null unique`), populated by an Alembic backfill and by the bot at `/join`.

Rule:

1. Lowercase the display name.
2. Replace runs of any non-`[a-z0-9]` characters with a single `-`.
3. Trim leading/trailing `-`.
4. If the result is empty (e.g. all-emoji name), fall back to `player-{first 8 of players.id}`.
5. If the result collides with an existing slug, append `-2`, `-3`, ... until unique.

Examples (real production names):

| display_name        | slug                |
|---|---|
| `nlaframboise`      | `nlaframboise`      |
| `Neo (Marc)`        | `neo-marc`          |
| `Mike Provencher`   | `mike-provencher`   |
| `Luke (lukkentopia)`| `luke-lukkentopia`  |
| `HAS510`            | `has510`            |

Renames don't update the slug — first-seen freeze keeps URLs stable. Users who want a new slug `/relink` (out of scope for v1; for now treat the slug as immutable post-`/join`).

---

## Per-archetype leaderboard

Alongside the main set leaderboard, the frontend exposes a per-archetype leaderboard: "best UW drafter for SOS," "best BG drafter," "best 5-color drafter." Reached by selecting an archetype on a set page; switches the data source to `public_archetype_leaderboard` rather than filtering existing rows client-side.

### Score definition

Per-archetype score uses **the same `compute_score` formula as the main leaderboard** (`bot/scoring.py`), run on the player's `draft_events` restricted to that archetype. Subset replay: *"if UW were your only deck, this is your score."*

The formula is non-linear (`trophies × points × trophy_rate × shrinkage`, with a special LCQ Draft 2 rule), so per-archetype scores do **not** sum to the main score across archetypes — they're a different question, not a decomposition. The UI labels this clearly so users don't try to reconcile the two totals.

The formula is additive across format groups (Premier, Trad, Sealed, Quick, LCQ), so the per-(player, set, archetype) score sums Premier-UW + Trad-UW + Sealed-UW + ... cleanly. Format-scoped archetype boards (UW Premier in isolation) are deferred — they'd need a third partition key in the view.

### Archetype normalization

`draft_events.colors` follows 17lands convention: uppercase = main colors, lowercase = splash. The view extracts main colors only, sorted in WUBRG order. Splashes are dropped.

| Raw `colors` | Normalized archetype |
|---|---|
| `WU` | `UW` (sorted WUBRG) |
| `WBg` | `BW` (g splash dropped) |
| `Wu` | `W` (mono, u splash dropped) |
| `WUg` | `UW` |
| `WUBR` | `UWBR` → sorted → `WUBR` |
| `` (colorless) | `` |

This collapses the archetype space to: 5 mono, 10 pairs, 10 trios, 5 four-color, 1 five-color, 1 colorless. A given set surfaces only a subset in practice.

### Qualifying and display

- A player appears on an archetype's leaderboard if they have **≥1 event** in that (set, archetype) cell.
- Players with 0 trophies in the archetype score 0 by formula construction. They still appear, sorted to the bottom, with their W/L/winrate visible — useful for "I played UW a lot but didn't trophy."
- Default sort: `score DESC`, with `winrate DESC` as tiebreaker (resolves the cluster of 0-point players at the bottom).
- Columns: rank, name, avatar, points, trophies, wins, losses, winrate, events.
- Other columns are sortable for visual exploration, but **rank is always defined by points**.

### Empty cells

If no player has any events in a given (set, archetype) cell — e.g. nobody has played 5-color in SOS — the archetype is grayed out in the picker for that set. Computed cheaply from the view: `archetype` values present in the `public_archetype_leaderboard` rows for the set.

---

## URL structure

Vite `base = '/leaderboard/'`. All routes below are relative to that base.

| Route | Query params | View |
|---|---|---|
| `/` | — | Redirect to `/{active_set_code}` |
| `/{setCode}` | `format`, `archetype` | Leaderboard for that set, optionally filtered/switched |
| `/player/{slug}` | `set` | Player profile, optionally scoped to a single set |

Filter dropdowns update query params via React Router's `useSearchParams`. TanStack Query caches per data-source key:

- **No filter or `?format=...` only** — reads `public_leaderboard`; format is a client-side reduction over cached rows.
- **`?archetype=...`** — switches to `public_archetype_leaderboard`, cached under a separate key per (set, archetype). Different scoring (subset replay), so it's a fundamentally different dataset.
- **`?archetype=...&format=...`** — combination is deferred (see *Out of scope*); for v1, picking an archetype clears or ignores the format filter.

---

## Repo layout

```
frontend/
├── src/
│   ├── main.tsx                     # entry: Router + QueryClient + Supabase client
│   ├── App.tsx                      # layout, header, footer
│   ├── routes/
│   │   ├── leaderboard.tsx
│   │   └── player.tsx
│   ├── components/                  # presentational only
│   │   ├── LeaderboardTable.tsx
│   │   ├── LeaderboardRow.tsx
│   │   ├── SetSelector.tsx
│   │   ├── FormatTabs.tsx
│   │   ├── ArchetypeFilter.tsx
│   │   └── PlayerAvatar.tsx
│   ├── data/
│   │   ├── supabase.ts              # supabase-js client init
│   │   ├── adapter.ts               # snake_case → camelCase
│   │   ├── queries.ts               # useLeaderboard, usePlayerProfile, useDraftEvents
│   │   └── fixtures/                # hand-crafted sample data, one per scenario
│   │       ├── leaderboard-sos.ts
│   │       ├── leaderboard-ecl.ts
│   │       └── player-clx123.ts
│   ├── types/
│   │   └── leaderboard.ts
│   └── style/                       # tbd by Claude Design
├── public/                          # static assets
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

Production build outputs to `frontend/dist/`. Cloudflare Pages publishes from there. The existing `web/index.html` placeholder stays live until the React app is ready to swap publish paths.

---

## Avatar plumbing

To render Discord avatars on the leaderboard, the bot needs to capture `avatar_hash` per player. `discord_id` already lives on `players`.

**Backend prep tasks** (separate phase, before frontend ships avatars):

1. Alembic migration: add `players.avatar_hash text` (nullable).
2. `/join` and `/relink` capture `interaction.user.avatar` (the hash, not the URL) and persist it.
3. `!refresh` re-fetches each linked user via `bot.fetch_user(discord_id)` and updates the hash if it changed (cheap; once per refresh per active player).
4. `public_leaderboard` view exposes the precomputed `avatar_url` (so `discord_id` never reaches the browser).

**Frontend**: `<PlayerAvatar avatarUrl={row.avatarUrl} displayName={row.displayName} />` renders the image when `avatarUrl !== null`, falls back to initials otherwise. No avatar = no plumbing problem.

---

## Future LLU integration

Two paths stay open without code changes, by virtue of `base = '/leaderboard/'` and only ever using React Router's `<Link>` (never absolute hrefs):

1. **Same SPA, expanded routes** — when `limitedlevelups.com` becomes a real React site, the leaderboard becomes one section sharing layout/nav. The `/leaderboard/*` routes plug in directly.
2. **Subpath reverse-proxy** — leaderboard stays its own Cloudflare Pages deploy; LLU site reverse-proxies `/leaderboard/*` to it via a Cloudflare Worker. Best if LLU uses a different stack.

Things to **not** do, to keep both options open:
- Hard-code `dischord.pages.dev` anywhere
- Build absolute paths instead of `<Link>`
- Bake the leaderboard into a layout that assumes it's the root of its app

---

## Phasing

**Phase 1 — backend prep**
- Enable RLS on all base tables
- Add `players.slug text not null unique` column + Alembic migration with backfill (rule in *Slug generation* section); bot populates new slugs at `/join`
- Add `player_archetype_scores` table + Alembic migration (parallels `player_set_scores`)
- Extend `!refresh` to compute per-(player, set, archetype) scores via `compute_score` over WUBRG-normalized `draft_events`, write to `player_archetype_scores`
- Create the six `public_*` views and grant `SELECT` to `anon` (`public_archetype_leaderboard` thinly joins the precomputed table with `players` and `sets`, computes `rank` via window function; `public_recent_trophies` filters `draft_events` to `is_trophy = true` and joins to `players`)
- Avatar migration + bot capture (`/join`, `/relink`, `!refresh`)

**Phase 2 — frontend scaffold**
- `frontend/` Vite + React + TS scaffold
- React Router + QueryClient + Supabase client
- TS types matching the views
- Adapter
- One fixture (active set)
- One stub presentational component (LeaderboardTable rendering fixture data)
- Cloudflare Pages preview deploy from `frontend/dist/`

**Phase 3 — design exploration**
- Hand spec + fixtures to Claude Design for wireframe / visual direction work
- Receive 2–3 directions; pick a winner
- Lock component library / styling stack based on direction

**Phase 4 — implementation**
- Build out presentational components per the chosen direction
- Wire up TanStack Query against live Supabase views
- Idle-time prefetch of other sets
- Player profile page
- URL routing (set selector, filters)
- Cut over Cloudflare Pages publish path from `web/` → `frontend/dist/`

**Phase 5 — polish**
- Responsive desktop layout (extra columns / density)
- Avatar rendering with fallback
- Empty states, loading skeletons
- Lighthouse / a11y pass

**Reserved for later**
- Discord OAuth + personalized highlights
- Pod-draft tracking views
- Real-time leaderboard updates (Supabase Realtime)
- Rank movement arrows (▲▼)

---

## Open shape questions

- **Vibe / visual direction** — Claude Design will explore. Reference sites under research.
- **Component library / styling stack** — deferred to Phase 3, depends on chosen direction.
- **Brand inputs for Limited Level Ups** — logo, palette, name treatment TBD by user.

---

## Cross-references

- Project status: `STATUS.md`
- Pod-draft feature spec: `pod-draft-spec.md`
- Original product spec: `mtga-leaderboard-spec.md`
- Memory: `project_rating_per_set.md` — rating formula may vary per set; frontend must not assume one global formula forever.
