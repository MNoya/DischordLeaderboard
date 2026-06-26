# Pack 0, Pick 1 — Results Phase

## Overview

The final phase of the P0P1 contest. Once 17lands data finalizes (~28 days after the MSH voting deadline of 2026-06-23), the page reveals final standings: ballots ranked by the summed 17lands GIH win rate of their 8 picked cards, each player's personal result, comparison against the best-possible and most-popular teams, and an over/underrated highlights reel.

This is the phase deferred by `spec/p0p1-after-submissions-closed.md` ("Scoring mechanics, the results leaderboard, and the highlights reel ... are a separate phase") and is the counterpart to the voting phase (`spec/p0p1-voting-mvp.md`) and the post-submission popularity phase (`spec/p0p1-after-submissions-closed.md`), both of which are built and shipped.

**Layout is not locked.** The results leaderboard, team-comparison, and per-slot comparison UI go through `frontend-design` mockups for sign-off before implementation — not ASCII sketches.

## What the page shows after scoring

Results **replace** the popularity display as the headline once the contest is scored. All
surfaces inherit the existing P0P1 visual system — Bebas Neue display / Space Grotesk body /
JetBrains Mono tabular numerals; the dark mat palette; the 4px colored top-rail tile idiom; the
chamfer scorecard; the VS-divider modal; and the established accent meanings (green `#2ee85c`,
blue `#4aa8ff`, purple `#a98eff` for pick states; red `#ff5e5e` / teal `#22d4c0` introduced for
the highlights poles). No new visual identity — layouts below were validated against rendered
mockups. However, layouts are not final and subject to change during implementation.

Sections, in order:

### 1. Hero

Switches to a scored state ("Final standings / Results are in"), reusing `P0P1Hero`.

### 2. Your result (logged-in)

Headline strip in the **chamfer scorecard** language (`P0P1BallotScorecard`):

- Large rank `#14 / 87`, a `TOP 16%` percentile chip, and the `442.32 SUMMED GIH WR` score
  (summed GIHWR ×100, two decimals — kept labelled as GIH WR since it is literally the sum).
- Below a divider, the three-team comparison as horizontal bars: **YOU / CROWD / BEST**
  (your team, the most-popular-picks team, the best-possible team) with each team's summed
  score, so the spread to the best-possible team reads at a glance.

### 3. Results leaderboard

Rows in the 4px-accent-rail idiom (from the pick tiles):

- Rank (Bebas) · avatar · username · `SUMMED GIH WR` score (mono). Podium rows get a gold rail;
  the logged-in user's own row gets the green rail + a `YOU` tag and is auto-expanded.
- Avatars/usernames come from the Discord identity already resolved server-side
  (`avatar_hash` → CDN URL, as the main leaderboard view does).
- **Each row is clickable to reveal that user's full 8-card ballot** — an art-crop strip with
  per-slot color bars and each card's GIH WR. Public for every entrant, per the privacy decision.
- A card in the reveal strip can open the per-slot 3-way comparison (section 4).
- Mobile: ballot strip collapses 8 → 4 columns.

### 4. Per-slot 3-way comparison

Extends the existing 2-way `PickVersusCard` modal to three columns, now keyed on **GIHWR** (pick%
demoted to a small caption). Header = slot pip + slot label; columns separated by the VS divider.

- Columns: **CROWD FAV / YOUR PICK / BEST PICK**, each with GIHWR (mono), a win-rate bar, and card
  art. Green marks the strongest win rate; your pick shows a delta to best.
- Win-rate bars are scaled on a ~40–65% range (not 0–100) so differences are legible.
- State collapses: when your pick **is** the best, it drops to two columns and your side turns
  green with a "BEST PICK · YOU FOUND IT" ribbon (mirrors the existing `agreed` state); a rogue
  (low-popularity) pick takes the purple accent; when crowd fav and best coincide, that column
  doubles up ("CROWD & BEST").
- The slot-local "best pick" may differ from the card the best-_possible team_ uses for this slot
  (cross-slot uniqueness) — present so this reads as intended, not a bug.
- Mobile: three columns stack vertically (crowd → you → best); VS dividers flip horizontal.

### 5. Highlights reel

Two sections of tiles (`CommunityGrid` tile idiom — 4px rail, art crop, slot pip + label overlay,
card name):

- **OVERRATED** (red rail): "the crowd loved them, the win rate didn't."
- **UNDERRATED** (teal rail): "nobody wanted them, they quietly won."
- The signature element is the **per-slot rank gap** made literal on each tile:
  `POPULARITY #1  ▼ FELL 8  →  WIN RATE #9` (red, falling) / `POPULARITY #9  ▲ ROSE 8  →  WIN RATE #1`
  (teal, rising) — the card's standing in popularity vs in win rate within its own slot, and the
  distance between them. Plus a `PICKED BY %` vs `GIH WR` stat block.
- Cards below the ~500-GIH sample floor are excluded. Grid is 3 → 2 → 1 columns responsive.

## Scoring

- **Score = summed GIHWR** of a player's 8 picks (e.g. 4.42).
- **Incomplete ballots are ranked with a partial sum** — missing slots contribute 0, so they sink naturally. No exclusion or separate listing. Consistent with the existing `hasParticipated = scoringFilled > 0` logic in `useP0P1Ballot`.
- **Sample floor**: cards below the 17lands default visibility threshold (~500 GIH) are treated as missing data — they contribute 0 to a player's score and are excluded from the best-possible team. Prevents a low-sample fluke from dominating.
- **Ranking ties** on a continuous summed float are effectively impossible; no tiebreaker slot exists (it was removed from the format).

### Comparison teams

- **Best-possible team** and **most-popular team** are **legal ballots** — they respect the contest's no-duplicate-card-across-slots constraint (a small constrained assignment over the slots, not a per-slot argmax). They are real, attainable ballots, not an unreachable upper bound.
- Note the distinction: the per-slot comparison's "best pick" is the slot-local best card, which may differ from the card the best-possible _team_ uses for that slot (because the team optimizes across slots under the uniqueness constraint). These are two different "best" numbers by design and must be presented so the difference doesn't read as a bug.

### Highlights — per-slot rank gap

Within each slot, rank cards by pick-popularity and independently by GIHWR.

- **Overrated**: popular but low winrate-rank (everyone took it, it underperforms).
- **Underrated**: ignored but high winrate-rank (nobody took it, it's secretly strong).

Surface the top few across all slots (sorted by gap magnitude).

## Data approach

Currently, ranking cannot be done naively client-side: the frontend only sees the caller's own ballot (RLS) and per-slot aggregate counts (`public_p0p1_pick_stats`) — never other users' full ballots. The **fully-public, clickable-ballot** decision removes that barrier, enabling the project's native pattern (raw aggregates in `public_*` views, score computed live on read — no precomputed score tables).

> **Confirmed.** Client-side compute depends on exposing every voter's raw ballot in a public view (`public_p0p1_ballots`). That's a single RLS-bypassing view migration (no base-table policy change) — see Public views. The casual nature of the contest makes public ballots a non-issue; the only guardrail is not leaking the auth UUID or email. The server-side precompute fallback below is retained only as a contingency.

### Bot — minimal server work

1. **Fetch card ratings** from the 17lands public, no-token endpoint:
   `GET /card_ratings/data?expansion=MSH&format=PremierDraft&start_date=<MSH Arena release>&end_date=<scoring date>`
   returning per-card `gih_wr` and `# GIH` (the sample size) for the full set in one call.
2. **Store** into `p0p1_card_ratings(set_code, card_name, gih_wr, num_gih, format, fetched_at)`.
   New idempotent script `bot/scripts/score_p0p1.py` (or a card-ratings method on
   `bot/services/seventeenlands.py`), upsert so it can be rerun.

No Discord posting — website only.

### Public views (read by anon/authenticated, gated to appear only after scoring)

Opening up the ballots requires **no change to the `p0p1_entries` RLS policies** — the base
table stays locked (each user reads only their own rows). Instead, add an **RLS-bypassing
`public_*` view** (runs as owner), gated by the scoring date with `WHERE now() > '<scoring date>'`
— the exact pattern `public_p0p1_pick_stats` already uses. One new view migration mirroring an
existing one; low risk.

- `public_p0p1_card_ratings` — the ~256 rating rows.
- `public_p0p1_ballots` — every voter's `(slot, card_name)` plus a **display identity**
  denormalized from the Supabase `auth` schema (not `models.py` — auth-managed):
  `auth.users.raw_user_meta_data->>'user_name'` / `'full_name'` for the name and
  `->>'avatar_url'` for the Discord CDN avatar (ready-to-use, no `avatar_hash`→CDN step),
  joined by `user_id` exactly as `bot/scripts/p0p1_voters.py` already does. **Drop that script's
  `email` fallback** in the view; use a neutral `Anonymous entrant` label when no Discord name
  exists. **Never expose `auth.users.id` (the UUID) or email.**

The frontend pulls the whole ballots view in one request (~150 voters × 8 ≈ 1,200 rows). Clicking
a leaderboard row expands data already loaded — **no per-user fetch, no addressable handle**
(see Open / deferred).

### Frontend — computes everything in TS

New `frontend/src/data/p0p1Results.ts` (parallel to `frontend/src/data/scoring.ts`):

- per-user summed GIHWR (below-floor cards → 0), rank, percentile;
- best-possible and most-popular teams (constrained assignment) and their summed GIHWR;
- per-slot rank-gap highlights.

Follows the existing `realApi.ts` / `mockApi.ts` / `api.ts` / `hooks.ts` data pattern. Mock mode generates synthetic ratings over the MSH card fixture.

## Open / deferred

- **Per-ballot links / public handle:** deferred. v1 is **expand-in-place** — click a leaderboard
  row to reveal the ballot inline, no per-user URL. A stable public handle is the hard part
  (many voters have no `players` row, and Discord usernames aren't stable/unique), so it's
  introduced later alongside the `contests` table and a real cross-contest history view, when the
  feature that needs it exists. Players already have `/player/{slug}` as their cross-contest home.
- **Results trigger (data- vs time-gated):** recommendation **data-gated** — flip to results when
  `public_p0p1_card_ratings` is populated (and past the scoring date), avoiding an empty board if
  the fetch hasn't run. Confirm at build time.
- **GIHWR window:** proposed `start_date` = MSH Arena release (from `bot/sets.py`), `end_date` = scoring date; a single frozen fetch. Confirm at build time.

## Reuse map

- `frontend/src/data/p0p1Stats.ts` — `groupBySlot`, `findExtremes`, `classifyYourPick`, `buildPickVersus` (extend for the 3-way comparison).
- Components: `PickVersusCard`, `P0P1BallotScorecard`, `PostVotingStats`, `CommunityGrid`, `FullBreakdownList`.
- `frontend/src/data/useP0P1Ballot.ts` — `isPastDeadline`, `hasParticipated`, dev presets for forcing the scored state.
- `bot/scripts/p0p1_voters.py` — identity-resolution SQL for the ballots view.
- `bot/services/seventeenlands.py` — add the card-ratings fetch.

## Verification

- Confirm `/card_ratings/data?expansion=MSH&format=PremierDraft` returns GIHWR + `# GIH` without a token.
- Mock mode with synthetic ratings: verify leaderboard, your-result, comparison teams (uniqueness constraint respected — no repeated card), highlights, logged-out state, desktop + mobile.
- Force the scored state via the existing p0p1 dev presets.

## Future / maybe

- Click a user to see their performance across past contests.
- DB-backed card data and a `contests` table (`set_code`, `voting_deadline`, `scoring_date`) when a second contest rotates in, replacing the MSH-hardcoded constants.
