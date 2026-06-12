# Homepage redesign — handoff

Status as of this session. The community-site homepage (`/`) was fully rebuilt into a one-screen dashboard. Everything is **frontend-only**, committed on `dev`.

## Update — polish pass

Big changes since the initial redesign (all in `HomePage.tsx` unless noted):

- **Tier panel → "SET REVIEW".** Marquee is now a true seamless infinite loop (per-card `pr-1.5` padding + `shrink-0` track + `translateX(-50%)`), shows **all main-set cards** (supplemental/bonus-sheet filtered via `inclusion_type`), constant pixel speed independent of card count (`TIER_SECONDS_PER_CARD`, no min floor), half-card stagger per row, **no animation on mobile** (`lg:animate-marquee`), native image quality (no forced aspect/lazy). Set chip is `square`, `w-[92px]`, opens on hover (click locks), chevron down→right.
- **Leaderboard.** Format rotation now **cross-fades** (two `absolute` layers, `animate-fadeIn`/`fadeOut`) instead of flicker — see `BoardSnapshot`/`layers`. Rows inherit `/leaderboard` styling (avatar, uppercase font-display name, mono rank, `hover:bg-surface2`) with full-bleed dividers. Set+format dropdowns are grouped right, equal `w-[92px]`, square. **Mobile shows top 8** via a fixed `h-[224px]` list (also gives the absolute crossfade layers a box).
- **Pod panel.** Static set logo (right corner, not a chooser). Live countdown moved onto the upcoming row; **upcoming links to the Discord event** (`discordEventLink`, guild id in `data/site.ts`) with a "View event on Discord" tooltip. Past rows: stacked date badge + bold champion + mana pips + `GiRoundTable`, "View seats, logs & replays" tooltip (shared `Tooltip`). Full-bleed dividers + green-tint hover.
- **Dropdowns squared** to match `/leaderboard`; "green = active only" (no green hover); square markers; `ALL FORMATS` has no swatch; order/labels from shared `FORMAT_OPTIONS`.
- **Panel** gained `headerBorder`/`actionBorder`; the action footer is a full-bleed flush hover band.
- **PageShell `fill`** sets `html` `scrollbar-gutter: auto` to kill the dead right gutter; `AppHeader` compensates its right padding by the measured `--app-scrollbar` so nav tabs don't shift between Home and other pages. Nav items `hover:text-green`.
- **Mobile order:** column wrappers use `display: contents` + per-panel `order-*`/`lg:order-none` so the stack is Identity → Episodes → Set Review → Leaderboard → Pods while desktop keeps 3 columns. Flush footer has no top margin (`mt-16` removed).
- **Identity panel:** Discord CTA centered with `DiscordIcon` (matches `/community`); social links are a full-width `grid-cols-3` row of icon buttons (Bluesky removed).
- **Footer disclaimer:** Fan Content Policy wording, two lines, smaller.
- New `TierSetDropdown` props: `square`, `openOnHover`, `triggerClassName`, `menuAlign: "center"`. New `fadeOut` animation in `tailwind.config.ts`.

## How to run / iterate
- Dev server: `cd frontend && npm run dev` → http://localhost:5173/ (Vite base is `/`, so the homepage is the root `/`; section routes are `/episodes`, `/tier-list`, `/leaderboard`, `/pods`, `/community`).
- Data mode defaults to `prod` (live Supabase + Libsyn + 17lands), so the page shows real data with no setup.
- Typecheck after edits: `cd frontend && npx tsc -b` (must stay clean).
- **Do NOT auto-verify via chrome-devtools** — the user actively monitors the running interface and reports back. Make the edit, typecheck, describe it.

## Layout (the dashboard)
`PageShell` in **`fill` mode** locks the page to one viewport on desktop (`lg`) so panels flex into the exact rendered space (no page scroll); mobile keeps normal stacking/scroll. Footer is flush (no top margin) in fill mode.

Three columns (`lg:grid-cols-[minmax(300px,360px)_1fr_minmax(300px,340px)]`), each a flex-col of panels that flex to fill height:
- **Left:** `IdentityPanel` (show blurb + host line + Join Discord CTA + social chips) then `TierPanel`.
- **Center:** `EpisodesHero` — 2×2 of the latest 4 episodes (big thumbnails).
- **Right:** `LeaderboardPanel` then `PodDraftsPanel`.

All panels share the `Panel` wrapper: header = title (Link) + optional centered `headerCenter` slot + optional `corner` node, body (flex-1), and a right-aligned `action` CTA footer (`self-end`).

## File map (what to edit)
- **`frontend/src/pages/HomePage.tsx`** — the whole homepage. Contains `Panel`, `IdentityPanel`, `TierPanel`, `EpisodesHero`/`HeroEpisodeCard`, `LeaderboardPanel`/`FormatDropdown`/`LeaderboardMiniRow`, `PodDraftsPanel`/`PodRow`, plus helpers (`sampleTiers`, `tierColor`, `splitPods`, `podWhenLabel`, `formatLabel`, `formatColor`). **Most tweaks live here.**
- `frontend/src/components/PageShell.tsx` — added `fill?: boolean` (viewport-lock + flush footer on `lg`).
- `frontend/src/components/SiteFooter.tsx` — added `flush?: boolean` (full-bleed, no top margin) + brand icons (react-icons/si: Apple Podcasts, Spotify, YouTube, RSS, Patreon). Copyright left, links right.
- `frontend/src/components/TierSetDropdown.tsx` — added `compact?` (smaller glyph/label/padding to match a panel title height) and `menuAlign?: "left" | "right" | "side-right"` (side-right = flyout to the right of the button, top-aligned). Label is Bebas Neue.
- `frontend/src/components/TierGrid.tsx` — **exported** `CardModal`, `CardPreview`, `PreviewAnchor`, and consts `PREVIEW_W/PREVIEW_RATIO/PREVIEW_EXTRAS_H/PREVIEW_GAP` so the homepage reuses the exact Tier List card preview/modal. Don't fork these.
- `frontend/src/data/tierList.ts` — `buildTierListSets(sets)` moved here (was in TierListPage) and exported; returns tier-list sets newest-first. TierListPage imports it now.
- `frontend/tailwind.config.ts` — added `marquee` keyframe + `animation.marquee` (used by tier rows).

## Behavioral contracts (so tweaks don't break intent)
- **Tier panel** uses the **latest available tier list** (`buildTierListSets(sets)[0]`, currently MSH), NOT the page's active set. It has its own compact set dropdown (`menuAlign="side-right"`) in the header corner. Rows = A/B/C/D letter grades (no F), each = grade cell (table-style, colored left strip via `tierColor()`) + a **marquee** of that grade's cards (top 20, `useTierList(uid, graders)` so cards carry grader grades). Hover a card → `CardPreview` (row pauses on hover); click → `CardModal` paging over all displayed cards. Action: "View Full Tier List" → `/tier-list/{set}`.
- **Leaderboard panel**: auto-rotates formats every 5s (`All Formats → Premier → Trad → …` from `useAvailableFormats`) with a fade (keyed remount). Header has a **set chooser** (`TierSetDropdown`, compact) centered and a **format chooser** (`FormatDropdown`, Bebas, short name on trigger / full names in menu) on the right. Picking a format manually **stops auto-rotation** (`manualRef`). Changing the set resets format to auto. Row count auto-fits available height (`LB_ROW_HEIGHT`, ResizeObserver). Pauses rotation on hover.
- **Pod panel**: up to 3 — 1 upcoming (NEXT, date/time) + 2 past (winner + record), via `splitPods`.
- **One-screen rule**: keep it fitting one screen on desktop. If a change adds height, the right-column list panels (leaderboard) auto-fit; tier rows flex. Don't reintroduce page scroll on `lg`.

## Placeholders / open copy (likely tweak targets)
- IdentityPanel: title "Limited Level-Ups / The show", blurb, host line (pulled from `data/site.ts` `HOST`). All editable copy.
- Episode thumbnails show the channel logo because the Libsyn feed has no per-episode art — real behavior.

## Scratch
- `design/` holds throwaway prototypes (`home-variations.html`, `tier-panel.html`) + screenshots used during exploration. Untracked. Safe to delete; not part of the app.

## Conventions reminder (from CLAUDE.md)
No inline comments; Bebas Neue = `font-display`, body = `font-body`, mono = `mono`; palette tokens `bg/surface/surface2/border/border2/text/subtle/muted/green/gold/teal/red`. Branch is `master`; never push. Commit backend first, leave frontend uncommitted until the user OKs.
