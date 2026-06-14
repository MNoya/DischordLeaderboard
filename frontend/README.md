# Limited Level-Ups — Leaderboard Frontend

Live React + TypeScript site that turns the static wireframes into a real,
clickable, mobile-responsive leaderboard. Drops onto `https://<domain>/leaderboard/`
as a static bundle; reads from a (mocked-for-now) Supabase-shaped API.

## Quick start

```bash
cd dboard-frontend
npm install
npm run dev      # http://localhost:5173/
npm run build    # → dist/ static bundle
```

## Routes (hash-based, work from any static host)

| Hash URL | Renders |
| --- | --- |
| `#/` | Leaderboard for the active set |
| `#/SOS` | Leaderboard for a specific set |
| `#/archetypes` / `#/SOS/archetypes/WR` | Archetype board |
| `#/player/chonce` / `#/SOS/player/chonce` | Player profile |

Set codes are 2–4 uppercase letters (matching `public_sets.code`).

## Source map

```
src/
  App.tsx                      Hash routes → pages
  main.tsx                     React Query + HashRouter wiring
  theme.ts                     Color tokens + font stacks
  styles.css                   Resets + .mono utility + scrollbar styling
  types/leaderboard.ts         camelCase mirrors of public_* views

  data/
    mockApi.ts                 Promise-returning fetchers (Supabase-shaped)
    adapter.ts                 snake_case ↔ camelCase row converter
    hooks.ts                   useSets, useLeaderboard, usePlayerProfile, …
    fixtures/                  Hand-curated SOS data (48 players, full draft log)

  components/
    AppHeader.tsx              Top chrome + useIsMobile() breakpoint hook
    Brand.tsx                  ALogo, AWordmark, AAvatar, Trophy, SetGlyph
    ManaPips.tsx               <Pip>, <Pips colors="WRu">
    SetSwitcher.tsx            Desktop chips + mobile sheet
    FilterDropdown.tsx         Native <select> styled to match
    LeaderboardSidebar.tsx     Top archetypes + recent trophies
    StatChip.tsx               Mobile stat tile

  pages/
    LeaderboardPage.tsx        Mobile + desktop, expandable rows
    PlayerPage.tsx             Hero + stat strip + format/archetype/color
                               breakdown + filterable draft log
    ArchetypePage.tsx          Subset-replay board with archetype switcher
```

## Wiring the real backend

Every component reads through `data/hooks.ts`. To switch from fixtures to
Supabase:

1. In `data/mockApi.ts`, replace each function body with a
   `supabase.from('public_*').select(...)` call against the curated views.
2. Run rows through `data/adapter.ts` to get camelCase types.
3. Leave `hooks.ts`, `pages/`, and `components/` untouched.

Hook signatures already match the spec's view boundaries 1:1.

## Deploy

`npm run build` emits a static `dist/`. `vite.config.ts` sets `base: "/"`, so the
app serves from the domain root with the leaderboard as one section (`/leaderboard`).
