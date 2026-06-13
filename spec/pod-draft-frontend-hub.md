# Pod Draft — frontend hub + data integration

Status doc for the `/pods` frontpage work. Phase 1 (UI + data layer + backend views) shipped on branch `pod-draft-replays`.

## Shipped

### Backend (migrations applied to prod)

- All 7 pending migrations from `o5e6f7g8h9i0` → `w4p5q6r7s8t9 (head)` applied to prod Supabase.
- New views (commit `b571c7a`):
  - `public_pod_draft_events` — per-event summary with derived slug (regex from `name`), `total_rounds` (MAX(round) from matches), champion (placement=1) info via LATERAL join, `participant_count`, `is_finalized`.
  - `public_pod_draft_event_participants` — full participant rows joined with `players` for slug/avatar.
- Bot announcement URL: `/pod/<slug>` → `/pods/<slug>` (`bot/services/pod_tournament.py`, commit `251f764`).

### Frontend (committed on branch, not yet merged to master)

- Routes: `/pods` (hub), `/pods/:slug` (detail). Both under Vite base `/leaderboard/` for now (top-level deferred).
- `PodDraftsPage` at `/pods`:
  - Leaderboard-style hero (`SetGlyph` + CURRENT SET label + set code + set name + date range + week).
  - Set switcher filtered via `usePodSetCodes()` ∩ `useSets()` — hidden when only one set has pods.
  - Side-by-side layout on desktop: standings table left, events list right.
  - Events row: full-width clickable header toggles inline standings; expanded block is a `<Link to="/pods/:slug">` with a `ChamferedButton` "VIEW BREAKDOWN" CTA matching the leaderboard's "VIEW PROFILE" pattern.
  - Standings rows: plain numeric rank + avatar + name + colors (pips) + record + per-row "VIEW DECK" button (opens screenshot in new tab; click stops Link propagation).
  - Simplified leaderboard table (no `score` column; sort locked to `trophies DESC, wins DESC, events ASC`).
- Types: `PodEventSummary`, `PodEventParticipantRow`, `PodLeaderboardRow` (`frontend/src/types/leaderboard.ts`).
- Data layer: `fetchPodEvents`, `fetchPodEventParticipants`, `fetchPodLeaderboard`, `fetchPodSetCodes` — mock + real + hooks. Mock derives from `podSos3Fixture` + 2 synthetic event summaries.
- Shared components extracted for cross-page consistency: `HeroSection` (gradient), `MobilePageHeader`, `RankBadge` (sm/md/lg), `ChamferedButton` (already existed, now used in pod hub too).
- Git cleanup: `frontend/node_modules` untracked (was committed before .gitignore rule landed).

## Remaining work

### 1. Backfill manually-seeded pod data (one-shot)

Pods 1/2/3 in prod were seeded by `bot/scripts/import_pod_draft_history.py` before `deck_colors` and `deck_screenshot_url` columns existed. Both fields are NULL for all 24 participants today, so the new views render empty pips and no VIEW DECK buttons.

- User to provide `(event_name, display_name) → (deck_colors, deck_screenshot_url)` tuples in plain text.
- Write `bot/scripts/backfill_pod_deck_data.py` — inline tuple list; `UPDATE pod_draft_participants SET deck_colors=?, deck_screenshot_url=? WHERE event_id=(SELECT id FROM pod_draft_events WHERE name=?) AND display_name=?`.
- Run once against prod. Future bot-flow pods will populate these automatically.

### 2. Port `PodPage` (`/pods/:slug`) off the fixture

Today it imports `podSos3Fixture` directly. Needs to read real data.

- Add a `fetchPodEvent(slug)` (or compose `fetchPodEventParticipants` + new fetchers for matches and replays) returning a `PodEvent`-shaped composite.
- New fetchers: `fetchPodEventMatches(eventId)` over `public_pod_draft_event_matches`, `fetchPodEventReplays(eventId)` over `public_pod_draft_replays`.
- Add `usePodEvent(slug)` hook.
- Wire `PodPage` to the hook; remove the fixture import.

**Open question — seat ordering for the radial table**: `pod_draft_participants` has no `seat_index` column. The PodTable component's radial layout currently consumes `seatIndex` from the fixture. Options:

- Add `seat_index INTEGER NULL` to `pod_draft_participants` via migration; backfill for the 3 historical pods (likely deterministic from existing data); future bot writes set it during lobby formation.
- Or derive deterministically on read: sort by `(placement NULLS LAST, display_name)` and assign 0..7. Stable but visually arbitrary vs the actual draft seating.
- Recommend the migration path — seat order is real data, not display sugar.

### 3. Top-level `/pods` route (done)

`/pods` is a top-level route: Vite `base: "/"`, no React Router `basename`, and `functions/_middleware.ts` handles multiple top-level paths. The URL is `dischord.pages.dev/pods` (and `limitedlevelups.com/pods` at launch). Existing `/leaderboard/...` URLs keep resolving as routes inside the SPA.

Best done as a separate focused PR alongside the custom-domain swap.

### 4. Merge `pod-draft-replays` → `master`

Feature branch carries the new views migration + the URL change + the entire frontend hub. Once the page is verified against real prod data (after the backfill or independently), merge to master and push.

### 5. Optional polish

- Per-set pod count badge in the set switcher (e.g., `SOS (3)`).
- `DeckScreenshotModal` integration on `/pods` event rows so VIEW DECK opens a modal instead of `window.open(_, "_blank")`.
- Hook the existing `usePodEventParticipants` cache as a prefetch when a row is hovered, so first click feels instant.
- Mobile event-row layout review — currently mirrors desktop (clickable header + expand). Verify on small screens.

## File map (this work)

- `alembic/versions/w4p5q6r7s8t9_public_pod_draft_events_view.py`
- `bot/services/pod_tournament.py` (announcement URL only)
- `frontend/src/components/HeroSection.tsx` (new)
- `frontend/src/components/RankBadge.tsx` (new)
- `frontend/src/components/PageNav.tsx` (gained `MobilePageHeader` export)
- `frontend/src/pages/PodDraftsPage.tsx` (full rewrite from stub)
- `frontend/src/pages/PodPage.tsx` (back-button label + URL; still on fixture)
- `frontend/src/types/leaderboard.ts` (3 new types)
- `frontend/src/data/{api,mockApi,realApi,hooks}.ts` (4 new fetchers + 4 new hooks)
- `frontend/src/data/fixtures/pod-events.ts` (new)

## Branch state

```
d91be67 Pod Draft: hub page — side-by-side standings + events on desktop
b76f839 Stop tracking frontend/node_modules
bf636b5 Pod Draft: hub page (/pods) with events list + simplified leaderboard
251f764 Pod Draft: announcement Replays button points to /pods/<slug>
b571c7a Pod Draft: public_pod_draft_events + participants views for the hub page
(+ later WIP commits on top adding view-deck column, plain-number rank, hero polish)
```
