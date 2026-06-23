# Pack 0, Pick 1 — Post-Submission Display

## Overview

Once the submission deadline passes (~June 23 for MSH), the P0P1 page locks picks and enters a waiting period until the scoring date (~4 weeks after set release). During this window the page should show community pick statistics so users have a reason to come back.

This spec covers **only the post-submission display**. Scoring mechanics, the results leaderboard, and the highlights reel (best possible team, overrated/underrated cards, etc.) are a separate phase.

## What the page shows after the deadline

### 1. Hero section adapts

- The countdown switches from "Closes in X days" to "Results in X days" targeting the scoring date. Show hours when it's less than 2 days remaining.
- Intro text updates to something like: "Picks are locked. Scoring begins when 17Lands data is finalized."
- The progress bar (`belowIntro` slot) is replaced with a total voter count: "87 players submitted entries."
- Logged-out users still see aggregate stats but no personal pick comparison.

### 2. User's locked roster (already implemented)

The RosterStrip / SlotCard tiles remain in locked mode showing the user's picks. Each tile gains a small inline badge: **"Picked by X%"** — showing what percentage of other players chose the same card for that slot. Only visible for logged-in users who have picks.

Some other situations we might want to account for:

- User who has submitted some picks but not the whole thing
- User who has logged in but not submitted any picks
- Non-logged in user - we could show something to drive engagement for the next round

### 3. Per-slot popularity

Exact design pending mockups. Initial idea — for each of the 8 slots, show:

- **Most popular card**: art crop, card name, mana cost, pick count and percentage.
- **Least popular card**: same display, but the card with the fewest picks among cards that were actually chosen. (Not "cards nobody picked" — that's the unpicked pool, which is less interesting.) - "rogue picks"

Presented as a grid matching the RosterStrip layout (8 columns on desktop, stacked on mobile). Reuses existing visual components (`ManaCost`, `SlotPip`, `CardImagePreview`, `SectionLabel`). Layout and presentation may change after mockups.

### 4. Full card pick breakdown (stretch goal)

A scrollable table of every card that was picked by at least one player, sorted by total pick count descending. Each row:

- Rank number
- Card art thumbnail (small)
- Card name
- Mana cost (`ManaCost` component)
- Slot color pip (which slot it was picked in)
- Pick count
- Percentage bar (inline, like a horizontal bar chart)

This is a nice-to-have. We'll size the effort during implementation and decide whether to include it in the initial release.

---

## Data approach

### Public Postgres view (not a precomputed table)

The `p0p1_entries` table is small — at most ~200 users × 8 slots = ~1,600 rows. A `GROUP BY` + `COUNT` is sub-millisecond. No precomputed snapshot table or script needed.

A new view `public_p0p1_pick_stats` aggregates pick counts per `(set_code, slot, card_name)`:

```sql
CREATE OR REPLACE VIEW public_p0p1_pick_stats AS
SELECT
    set_code,
    slot,
    card_name,
    COUNT(*)::int AS pick_count,
    ROUND(COUNT(*)::numeric * 100.0 /
        NULLIF(SUM(COUNT(*)) OVER (PARTITION BY set_code, slot), 0), 1
    ) AS pick_pct
FROM p0p1_entries
WHERE now() > '2026-06-23T15:00:00Z'
GROUP BY set_code, slot, card_name;
```

Key design points:

- **View bypasses RLS** — runs as the view owner (same pattern as `public_leaderboard` reading `player_set_scores`). The underlying `p0p1_entries` table keeps its user-scoped RLS for direct authenticated access.
- **Aggregates only** — the view exposes card name + count, not which user picked what. No privacy concern.
- **Hidden until deadline** — the `WHERE now() > ...` clause returns empty results before voting closes, preventing aggregate stats from influencing picks during voting. The MSH deadline is hardcoded in the view SQL for now.
- **`GRANT SELECT TO anon, authenticated`** — readable by all frontend visitors, same as other `public_*` views.
- **Total voters derivable** — since every voter picks exactly one card per slot, `SUM(pick_count)` for any single slot = total voter count. No separate query needed.

The frontend cross-references the user's own picks (already fetched via the existing RLS-scoped `p0p1_entries` query) against the view rows to compute "picked by X%."

### Hardcoded deadline in the view (temporary)

The `WHERE now() > '2026-06-23T15:00:00Z'` is specific to the MSH contest. When a second contest is created, we'll introduce a `contests` table (holding `set_code`, `voting_deadline`, `scoring_date`) and update the view to join against it. For a single contest this is simpler than building the table upfront.

---

## What this does NOT cover (deferred to scoring phase)

- **Scoring mechanics**: fetching 17lands GIH win rates (PremierDraft format, new data path), computing per-user totals, ranking
- **Results leaderboard**: final standings after scoring
- **Highlights reel**: best possible team, top overrated cards (high pick rate + low GIH WR), top underrated cards (low pick rate + high GIH WR), most popular team vs. field
- **Card ratings table**: `p0p1_card_ratings(set_code, card_name, gih_wr, format)` storing GIH WR for all eligible cards (not just picked ones)
- **Scoring script**: manual trigger (`python -m bot.scripts.score_p0p1`), idempotent (upsert) so it can be rerun for informal midway check-ins posted to Discord
- **Midway check-in**: informal — rerun scoring script partway through, post results to Discord. No UI feature.
- **Contests table**: `set_code`, `voting_deadline`, `scoring_date`, plus optional `tiebreaker_label` / `tiebreaker_constraint`. Bot-managed via seed script, read through `public_p0p1_contests` view. Build when second contest rotates in.
- **Tiebreaker slot**: removed from the contest format. 8 scoring slots only.

---

## Frontend implementation notes

### Data layer

- New type `P0P1PickStat { setCode, slot, cardName, pickCount, pickPct }`
- New API function `fetchP0P1PickStats(setCode)` querying the view
- New React Query hook `useP0P1PickStats(setCode)` — only enabled when past deadline
- Mock API returns synthetic stats generated from the card fixture
- Follows existing `realApi.ts` / `mockApi.ts` / `api.ts` / `hooks.ts` pattern

### New component

`PostVotingStats.tsx` — renders sections 3 and 4 (per-slot popularity + stretch goal breakdown). Receives pick stats, card fixture data, and the user's picks as props.

### Modified components

- `P0P1Page.tsx` / `P0P1MobileView.tsx` — render `PostVotingStats` when `isPastDeadline`, add "picked by X%" badge to roster tiles, adapt hero section
- `Countdown.tsx` — support scoring countdown mode ("Scoring in X days" vs "Closes in X days")
- `p0p1Slots.ts` — add `P0P1_SCORING_DATE` placeholder constant

### Testing approach

- Force `isPastDeadline = true` in `useP0P1Ballot` during development
- Mock mode with synthetic stats for all UI sections
- Verify desktop and mobile layouts
- Verify logged-out state (aggregate stats visible, no personal pick badges)
