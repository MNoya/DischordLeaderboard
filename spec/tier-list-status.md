# Tier List — status & resume-cold notes

_Last updated: 2026-06-11_

## TL;DR

Native React tier list at `/tier-list` and `/tier-list/:setCode`, fed by 17lands tier-list data through a same-origin proxy. **Base feature deployed to `master` in commit `d4eb8f0`** (and `llu` fast-forwarded to match); both branches still **ahead of their remotes — not yet pushed**. Everything dated 2026-06-10/11 below (trend filter, grades panel, right-side hover, Prev/Next modal, last-updated line, Pages Function proxy, MSH fixture) is **uncommitted working-tree**, bundled with the episodes/community/home site work. Tier List is now a visible navbar tab (second, after EPISODES) in that uncommitted work.

## What shipped (committed `d4eb8f0`)

Files in the commit:

- `frontend/src/data/tierList.ts` — `TierCard` type, `TIER_ORDER`, `TYPE_GROUPS`, `MANA_VALUE_BUCKETS`, rarity tables, filter model, `tierFilterOptions`, `useTierList(uid)`, `fetchTierList`.
- `frontend/src/components/TierGrid.tsx` — `DesktopGrid` (7 color columns × tier rows, sticky pip header), `MobileTiers`, `CardBar`, `CardPreview`, `CardModal`, `columnPipClass`.
- `frontend/src/components/TierFilterBar.tsx` — `FilterGroup` + `IconToggle`; RARITY / TYPE / MANA VALUE / SET GROUP.
- `frontend/src/components/TierSetDropdown.tsx` — set-title dropdown with `LIVE` / `PREVIEW` tags.
- `frontend/src/pages/TierListPage.tsx` — filter state owner; set is URL-driven; `buildTierListSets` merges live backend sets with preview-only sets.
- `frontend/src/App.tsx` — `/tier-list/:setCode` route.
- `frontend/src/data/constants.ts` — `TIER_LIST_UIDS` (SOS/TMT/ECL/TLA), `TIER_LIST_DATA_BASE`, empty preview/override maps.

## Uncommitted on top (2026-06-10/11 session)

### Grades model — Set Review vs Updated

The list is ONE consensus list per set (the hosts' 17lands tier list). Two grades per card derive from it:

- **Set review grade** = `trend_from` (the grade when the list was created), falling back to `tier` for never-regraded cards.
- **Updated grade** = `tier` (current; what the grid sorts by). Drives the ▲/▼ trend.
- **Host grades (Alex/Marc)** — `TIER_LIST_GRADERS` in constants maps set → `{name, uid}[]` of locked review lists (both public on 17lands for MSH, 334 cards each). `useTierList(uid, graders)` fetches them (`staleTime: Infinity`) and joins each grader's tier onto consensus cards by normalized name. Shown **only until a card's first regrade**; once `trend` exists the panel shows Set Review | Updated and hides the hosts.
- An Alex/Marc-free intermediate design was tried and reverted same-day; the grader plumbing was deleted and restored — don't re-litigate, the conditional display is the decision.
- `TREND_LABEL` copy is "Up/Down since the set review"; bar tooltips append the move, e.g. `(B → A-)`.

### TREND filter

- Fifth filter group ("TREND", right of SET GROUP): green ▲ / red ▼ `IconToggle`s, counts in tooltips via `tierFilterOptions().trends`.
- `TierFilters.trends`: one direction selected → non-matching cards **hidden** (normal filter semantics). **Both selected → nothing hidden; unchanged cards render dimmed** (`isCardTrendDimmed` → `opacity-35 grayscale`). This is the one deliberate exception to "filtered-out cards are hidden, not dimmed".
- Trend toggles count toward the mobile Filters badge.

### Trend arrows on card bars

- Magnitude = `trendSteps(card)`: `TIER_ORDER` distance from `trend_from` to `tier`, capped at 3 for display.
- Stacked **vertically**, fast-forward style: full-size 13px glyphs overlapping via `-mt-[7px]`, upper arrow painted over the lower (descending z-index). `TREND_*` constants live in `tierList.ts` (shared with the filter bar).
- Comment/synergy/buildaround badges bumped to 14px.

### Hover preview (desktop)

- **Always opens to the RIGHT of the bar**, vertically centered on it and viewport-clamped; mirrors to the left only when the rightmost columns lack room. Internal order is fixed: grades panel → card image → comment (centered). No more above/below flipping — that was a UX complaint (unpredictable grade/comment position).
- Frame mimics deck-site hovers: 1px `border-white/60`, translucent gray mat `PREVIEW_MAT = rgba(29,35,48,0.97)`, 6px padding, `rounded-xl`, image `rounded-[10px]`. Chevron is two SVG triangles (white/60 silhouette + inset mat fill) overlapping the border by 1px — no stroke, nothing pokes outside.
- `PREVIEW_W = 260` (Scryfall `large` source is 672×936, plenty of headroom). `PREVIEW_EXTRAS_H` pads the height estimate for the grades panel.
- Grades panel: white captions ("SET REVIEW" / "UPDATED"), 26px grades, `TEXT_OUTLINE` on all panel text and arrows (mat is translucent), no divider. Host-grade rows are a centered 2-col grid, grades left-aligned.

### Mobile card modal

- Modal state lifted from `CardBar` to `MobileTiers`: it flattens the visible (post-filter) cards in display order and tracks selection by `card_id`.
- Bottom pager: ‹ / › square buttons + `n / total` position; steps across the whole visible sequence (crossing color rows and tiers); buttons disable at the ends. Filter changes that remove the selected card close the modal.
- Same frame styling as the hover preview.

### Page identity & last-updated

- `ListMeta` under the set title (both layouts): `SET REVIEW GRADES · LAST UPDATED 2D AGO` (existing `relativeTime` helper; omits the updated half when no timestamp).
- Rejected on the way here (don't revisit): identity banner above the grid, ⓘ + `#grades` info modal (`TierInfoModal.tsx`, deleted), and an `AppHeader` tagline slot — all removed in favor of the under-title line.

### Data plumbing

- `fetchTierList` returns `{ cards, lastUpdated }`; handles both response shapes (bare array = cards only; dict = `ratings` + `last_updated`, normalized from space-separated UTC to ISO `Z`). `useTierList` exposes `lastUpdated`.
- **Endpoint discovery:** 17lands has two routes — `/card_tiers/data/<uid>` (bare array, CORS-enabled) and `/data/tier_list/<uid>` (dict with `last_updated`, **no CORS**). To get the timestamp browser-side:
  - **`functions/api/tier-list/[uid].ts`** (repo-root Pages Function, ships automatically via `wrangler pages deploy` in `deploy-pages.yml`) proxies `/data/tier_list` with a 10-minute edge cache. Pages free tier (100k req/day) makes this effectively free.
  - **Dev**: vite proxy `/api/tier-list → https://www.17lands.com/data/tier_list`. Same path both envs; `npm run preview` has neither, so tier data 404s there.
  - `TIER_LIST_DATA_BASE = "/api/tier-list"`.
- **MSH consensus list is a repo fixture**: `frontend/public/tier-fixtures/11bab….json` (329 cards, `last_updated` frozen at snapshot). `TIER_LIST_DATA_BASE_OVERRIDES` values are now **full fetch URLs** keyed by uid. The localhost:8008 preview server and `/local-tier` proxy are gone. Re-snapshot = one curl to `:8008/data/tier_list/<uid>` (if that server runs again) or wait for 17lands.

### Page behavior

- `/tier-list` without a set code defaults to the **newest set with a tier list** (`tierListSets[0]`, sorted by startDate desc, previews included) — currently MSH — instead of the active leaderboard set.

### Site-work touchpoints from the same session (also uncommitted)

- Navbar order: EPISODES · **TIER LIST** · LEADERBOARD · POD DRAFTS · COMMUNITY; the SUPPORT CTA was removed from the header (Patreon now a `COMMUNITY_PLATFORMS` card on the Community page + footer link).

## Architecture (unchanged fundamentals)

- Client-side fetch per uid; one uid per set in `TIER_LIST_UIDS`. 17lands' grade is shown verbatim — no local scoring.
- `TierCard` carries `expansion` and `inclusion_type` for the SET GROUP filter; `trend` / `trend_from` for the trend features.

### Why native (not the iframe)

The first implementation embedded 17lands' page via `<iframe>`: cross-origin sizing was unreliable and styling was impossible. Rendering from the raw data lets us own the grid, filters, hover, and theming. The `via 17Lands` link still credits the source.

## Key UI decisions (so they aren't re-litigated)

- **Filtered-out cards are hidden, not dimmed** — except the both-trends-selected case, which dims unchanged cards by design. Column pips gray out when their column has no matches; grade row labels are never dimmed.
- Filters are include-semantics; empty group = no constraint. RARITY uses keyrune set symbols; TYPE merges Artifact/Enchantment/Planeswalker; MANA VALUE hides below 1150px on desktop; SET GROUP lists every expansion.
- Multicolor column pip = mana-font gold duotone glyph.
- Rarity accent bar: common `#ffffff`, uncommon `#707883`, rare `#a58e4a`, mythic `#bf4427`.
- Card names `line-clamp-2`; bar `min-h-[28px]`.
- Desktop header = 2-col grid (title + filters), third spacer column ≥1500px.
- Mobile filter panel behind a "Filters" toggle; tier groups separated by 5px gaps; mobile breakpoint is the site default (720px).
- Removed historically: per-set chip `SetSwitcher`, sticky "TIER LIST" label, Clear button, the 900px-breakpoint experiment.

## Open / pending

- **Push** `master`/`llu`; commit + ship the site work bundle (tier-list changes ride with it).
- **MSH cutover:** when 17lands hosts the consensus list publicly, delete the `TIER_LIST_DATA_BASE_OVERRIDES` entry and the fixture file — nothing else.
- Fixture `last_updated` is frozen until re-snapshotted.
- Hover height estimate (`PREVIEW_W × ratio + PREVIEW_EXTRAS_H`) ignores comment length — a very long comment can run past the viewport bottom.
- No Clear button: a Mana Value filter set wide then narrowed below 1150px can't be cleared without widening again.
- `trend_from` means "since this list's baseline snapshot" upstream — if 17lands ever re-baselines mid-format, "SET REVIEW" silently shifts meaning.
- Future idea (explicitly deferred): a 17lands data-driven grade as a third grade source.

## Resume cold

Current work lives in the `dev` working tree (uncommitted), on top of `master`'s `d4eb8f0`. The feature is `frontend/src/pages/TierListPage.tsx`, `frontend/src/components/Tier*.tsx`, `frontend/src/data/tierList.ts`, the tier-list bits of `frontend/src/data/constants.ts`, `functions/api/tier-list/[uid].ts`, and `frontend/public/tier-fixtures/`. Frontend typecheck: `cd frontend && npx tsc -b`.
