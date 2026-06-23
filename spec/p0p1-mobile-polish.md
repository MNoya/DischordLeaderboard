# P0P1 post-vote mobile polish — handoff

Mobile-focused polish of the post-vote (and pre-deadline) P0P1 page. **All of this work is uncommitted and lives in a git stash** (see "Resuming" below). Verified in DevTools at 390px (mobile) and 1280px (desktop) across the four dev-panel states. `tsc` clean.

## Resuming this work (read first)
- Branch: `p0p1-after-submissions`.
- The code + this spec are in a git stash labeled **`p0p1 post-vote design + dev toggle (mobile polish)`**. Restore with `git stash list` then `git stash pop stash@{N}` for that label (there's also an older `p0p1 mobile-polish WIP` stash from another session — don't grab that one).
- Run in **mock mode**: `frontend/.env.local` → `VITE_DATA_MODE=mock`, then `cd frontend && npm run dev`. Mock drives every state with synthetic data — no DB, proxy, or login.
- Switch states with the **DEV pill** (bottom-right, localhost dev builds only): Live / Closed·logged-out / Closed·complete / Closed·incomplete. Selection persists in localStorage.
- Unrelated working-tree changes belong to a **different session's leaderboard/scoring refactor** — not part of this work.

## Decisions taken (were open)
- **#5 logged-out count:** percentage, not hide — consistent with #7/#9, informative without exposing individual ballots.
- **#10 incomplete entries:** frontend only. Partial entrants see their picks with empty slots flagged; zero-pick logged-in users get a reworded box. The DB view's complete-only rule (`HAVING COUNT(*) = total_slots`) was **not** changed — counting partials toward the aggregates is still a backend decision.
- **Slot identity (#4):** restored the colored accent strip (from the voting grid) on Crowd Favorites tiles and breakdown headers, kept the `SlotPip` symbol too.

## Status per item

| # | Item | Status |
|---|------|--------|
| 1 | Post-vote copy + redundant count line | Done — "Picks are locked. Standings post once 17Lands win-rate data is in." + "{n} players in the running." (mobile + desktop) |
| 2 | "Crowd Favorites" top padding / centering | Done — title centered, subtitle block removed so it sits tighter |
| 3 | Drop "Most popular picks by slot" subtitle | Done |
| 4 | Unify on the compact 8-slot grid / strip colors | Partial — accent strips restored on Crowd Favorites + breakdown; SlotPip kept. A direction, not a finished redesign |
| 5 | Logged-out "N picked" meaningless | Done — shows "X%" |
| 6 | "submitted" wording | Done — "in the running" (hero) / "{n} players" (breakdown header) |
| 7 | Breakdown mobile typography + "N cards" + % | Done — removed "N cards", added "PICKED BY" % column, bumped fonts, accent strip per slot header |
| 8 | Breakdown as an 8-grid | Partial — restyled the accordion (accent strips, %, larger type); kept accordion interaction, not a literal grid |
| 9 | "Picked by X%" on own picks | Done — mobile chip, mobile carousel, desktop roster tile |
| 10 | Incomplete-entry handling | Done (frontend) — see below |

### #10 detail
- **Partial (≥1 pick):** "YOUR PICKS" + "{filled}/8 locked · empty slots score 0" note; filled picks render, empty slots flagged **NO PICK / Scores 0** (magenta). Verified via closedIncomplete preset (4/8).
- **Zero picks, logged in:** `IncompleteEntryMessage` reworded to a standalone box ("No picks locked this round." + Join the Dischord) — drops the "complete entry" framing. Not visually exercised (no dev preset triggers it); verified by code path only.

## Files in the stash (the polish)
- `frontend/src/data/p0p1Stats.ts` — `pickPctLabel` helper
- `frontend/src/components/p0p1/CommunityGrid.tsx`
- `frontend/src/components/p0p1/FullBreakdownList.tsx`
- `frontend/src/components/p0p1/IncompleteEntryMessage.tsx`
- `frontend/src/components/p0p1/P0P1Hero.tsx`
- `frontend/src/components/p0p1/P0P1MobileView.tsx`
- `frontend/src/pages/P0P1Page.tsx`
- Dev toggle (separate earlier work, same stash): `frontend/src/data/p0p1DevState.ts`, `frontend/src/components/p0p1/P0P1DevPanel.tsx`, `frontend/src/data/useP0P1Ballot.ts`
- Proxy fix: `bot/scripts/local_supabase_proxy.py` (allow the p0p1 view + serialize Decimal)

## Next polish pass — candidates
- **#4 + #8:** decide whether to push to a literal 8-slot grid breakdown and a single converged slot-identity treatment, or keep the current restyle.
- **#10 backend:** if partial entries should count toward the aggregate pick data (earlier lean: yes — can't win, but contribute), change the view's complete-only rule and the entry-count denominator.
- **Zero-pick incomplete box:** verify live (needs a logged-in user with no picks, or add a temporary dev preset).
- **Countdown fidelity (dev-only):** in forced "Closed" dev states the hero countdown still reads "Closes in…" because `CountdownStacked` reads the real deadline, not the dev override. Cosmetic, dev-only — fix if it bothers review.
