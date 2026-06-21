# P0P1 Contests — Data-Driven Config for Future Sets

## Context / motivation

`public_p0p1_pick_stats` (`alembic/versions/d5e6f7g8h9i0_public_p0p1_pick_stats_view.py`) currently
gates on `WHERE now() > '2026-06-23T15:00:00Z'`, treating early visibility of aggregate picks as
something to prevent. It isn't:

- **Scoring is fully external.** Ballots are ranked by 17lands GIH win rate of the picked cards,
  measured over the following 6 weeks (`spec/p0p1-voting-mvp.md:11`). That data doesn't exist at
  voting time, so seeing what others picked gives no edge — there's nothing to copy that improves
  your score.
- **The view is anonymous aggregate, never per-ballot.** It groups by
  `(set_code, slot, card_name)` over complete entrants only; no individual's picks are ever exposed,
  gated or not.

So the read gate is dropped entirely — `public_p0p1_pick_stats` becomes unconditionally public, same
as `public_p0p1_contests` and `public_cards`. The frontend keeps withholding the community grid /
`PostVotingStats` until the deadline, but that's now a **UX reveal moment**, not a security boundary;
the data underneath is public the whole time. The voting deadline (lock + reveal) becomes entirely
client-enforced — acceptable because reads are public by design and the write path
(`upsertP0P1Pick`) was already unguarded server-side.

What still needs fixing, independent of the gate: the deadline and set are a **single global
timestamp/constant** duplicated in the view literal **and** `frontend/src/data/p0p1Slots.ts:6`
(`P0P1_VOTING_DEADLINE`) / `p0p1Slots.ts:4` (`// TODO: get this data from the database`), kept in
sync by hand, and incapable of expressing a second contest with a different deadline. This matches
what the original spec already anticipated (`spec/p0p1-voting-mvp.md:113`: "A `contests` table …
would let deadlines be managed without code changes").

**Outcome:** a `p0p1_contests` table owns each contest's deadline and active-contest metadata as
data-driven config — not as an access-control mechanism. The frontend reads contest config from a
public view instead of hardcoded constants. Launching a new contest becomes "insert a row" — no
migration, no code change, and no per-contest editing of two synced literals.

## Data model

### `p0p1_contests` table

| Column            | Type        | Notes                                                            |
| ----------------- | ----------- | ---------------------------------------------------------------- |
| `set_code`        | text        | **PK**                                                           |
| `set_name`        | text        | not null — display name, e.g. "Marvel Super Heroes"              |
| `voting_deadline` | timestamptz | not null — write lock + frontend reveal moment                    |
| `scoring_date`    | timestamptz | not null — when results are scored (today = deadline + 28d)      |
| `is_active`       | boolean     | not null default true — the featured/default contest (see below) |

- All `DateTime` columns are `DateTime(timezone=True)` (TIMESTAMPTZ invariant).
- No RLS: read-only reference data, exposed via a public view; the bot is the only writer.
- Multi-row by design — one row per contest/set; historical contests stay with `is_active=false`.
- **`is_active` semantics**: exactly one row is `true` at a time — the contest bare `/p0p1` lands on.
  If no row is active the frontend falls back to the most-recent `voting_deadline`. Voting is enabled
  only when the selected contest is `is_active` **and** pre-deadline; every other contest is
  results-only read-only.

### Views

- **`public_p0p1_pick_stats`** (recreated): unchanged CTEs (`slot_counts`, `complete_entrants`),
  but the `WHERE now() > '2026-06-23T15:00:00Z'` gate is dropped — the view always returns
  aggregates for complete entrants, no `p0p1_contests` JOIN needed:
  ```sql
  FROM p0p1_entries e
  JOIN complete_entrants c USING (user_id, set_code)
  GROUP BY e.set_code, e.slot, e.card_name;
  ```
- **`public_p0p1_contests`** (new): `SELECT set_code, set_name, voting_deadline, scoring_date,
is_active FROM p0p1_contests;` — no `now()` gate (config is public).
- **`public_cards`** (new): `SELECT set_code, name, mana_cost, cmc, colors, rarity, type_line,
collector_number, image_small, image_normal, image_art_crop FROM cards ORDER BY
set_code, collector_number::int;` — public, no RLS.
- All three GRANT SELECT to `anon` + `authenticated` via the existing `pg_roles` guard block copied
  from `d5e6f7g8h9i0`.

### Source of truth — `bot/sets.py`

Add a `P0P1_CONTESTS` tuple parallel to `ALL_SETS` / `PREVIEW_WINDOWS`, with a small
`@dataclass P0P1ContestSeed(set_code, set_name, voting_deadline, scoring_date, is_active)`.
Seed the MSH row from the current literals (deadline `2026-06-23T15:00:00Z`, scoring `+28d`,
`is_active=True`). Contest config lives next to set-rotation config.

## Implementation

### Backend (commit first)

1. **Models** — add to `bot/models.py` (after `P0P1Entry`):
   - `P0P1Contest` — columns above.
   - `Card` — `(set_code, name)` PK, the 10 snake_cased fields matching the frontend `Card` type:
     `mana_cost, cmc, colors (ARRAY(Text)), rarity, type_line, collector_number, image_small,
image_normal, image_art_crop`.
2. **`bot/sets.py`** — add `P0P1ContestSeed` + `P0P1_CONTESTS` with the MSH row.
3. **Migration** — new revision, `down_revision = d5e6f7g8h9i0`:
   - `CREATE TABLE IF NOT EXISTS p0p1_contests (...)`.
   - `CREATE TABLE IF NOT EXISTS cards (...)`.
   - `CREATE OR REPLACE VIEW public_p0p1_pick_stats` dropping the global-literal `WHERE` gate
     (ungated, per above).
   - `CREATE OR REPLACE VIEW public_p0p1_contests`.
   - `CREATE OR REPLACE VIEW public_cards`.
   - GRANTs via the `pg_roles` guard block for all three views.
   - `downgrade()`: drop the three views, drop `cards`, drop `p0p1_contests`, restore the old
     global-literal WHERE on `public_p0p1_pick_stats`.
4. **Seed scripts** — both separate from `seed_sets` (which runs heavyweight leaderboard work):
   - `bot/scripts/seed_p0p1_contests.py`: idempotent upsert from `bot.sets.P0P1_CONTESTS`,
     mirroring `seed_sets.py:upsert_set`.
   - `bot/scripts/seed_cards.py`: idempotent upsert keyed `(set_code, name)`, **live Scryfall fetch**
     via the search endpoint (`set:<code>`, rarity common/uncommon/rare, no mythics), paginating
     `has_more`/`next_page`; model HTTP style on `bot/scripts/backfill_pod_draft_log.py`. Iterates
     the set codes in `P0P1_CONTESTS`. Assume Scryfall code == app set_code; verify MSH resolves.
     Map DFC/split cards via front face. **Exclude mythic rares** (filter `rarity != mythic` in the
     Scryfall query or post-fetch) — consistent with the contest rules and the existing MSH fixture.
   - Document both under CLAUDE.md "Common commands".

### Frontend (leave uncommitted for user review)

Contest metadata and card pool come from the DB. **Slot rules / predicate logic stay client-side.**

5. **Data layer**
   - `realApi.ts`:
     - Add `fetchP0P1Contest()` → `.from("public_p0p1_contests").select("*").eq("is_active", true)`;
       returns `{ setCode, setName, votingDeadline: Date, scoringDate: Date }`.
     - Add `fetchP0P1Contests()` → `.from("public_p0p1_contests").select("*")`; returns an array
       of all contests (for the multi-contest selector).
     - Rewrite `fetchP0P1Cards(setCode)` → `.from("public_cards").select("*").eq("set_code", setCode)`
       ordered by `collector_number::int`; snake→camel inline. (Currently ignores setCode and returns
       the MSH fixture.)
   - `mockApi.ts`: return a static MSH contest object for `fetchP0P1Contest` / `fetchP0P1Contests`;
     replace `fetchP0P1Cards` with a `generateP0P1Cards(setCode)` function that synthesizes 3–5
     fake cards per slot covering each slot's eligibility filter (right rarity/colors/typeLine for
     all 8 slots, no mythics, placeholder image strings). Follows the same pattern as the existing
     `generateP0P1PickStats()` — no fixture file, zero growth per future set. The `cards-msh.ts`
     fixture loses all consumers and can be deleted.
   - `api.ts`: wire the three new exports.
   - `hooks.ts`: add `useP0P1Contest()` and `useP0P1Contests()`.
6. **Thread through, drop the constants**
   - `useP0P1Ballot.ts`: consume `useP0P1Contest()`; derive `setCode` + `isPastDeadline =
contest && new Date() > contest.votingDeadline`. While loading (undefined), render a page
     skeleton — do not treat undefined as past-deadline, no hardcoded fallback.
     `isPastDeadline` is now purely a **UX flag** (no server gate backs it): it both locks voting
     and decides when the community grid / `PostVotingStats` become visible. The aggregate data
     itself (`public_p0p1_pick_stats`) is public throughout — the frontend chooses to withhold it
     pre-deadline as a reveal moment, not because it's protecting anything.
   - Replace constant imports in `AppHeader.tsx`, `P0P1Hero.tsx`, `P0P1MobileView.tsx`,
     `slotVisuals.tsx` with hook values. `slotVisuals.tsx:37` uses `P0P1_SET_CODE` at module scope
     for the keyrune class — pass `setCode` in as an arg.
   - `p0p1Slots.ts`: remove `P0P1_SET_CODE / P0P1_SET_NAME / P0P1_VOTING_DEADLINE /
P0P1_SCORING_DATE` (keep `SLOTS` + slot predicates); delete the TODO.

## DB-backed card pool

The `cards-msh.ts` fixture (256 cards, produced as a one-off Scryfall pull) becomes mock-only once
`seed_cards.py` and `public_cards` land. The frontend `Card` type shape (`types/p0p1.ts`) is
unchanged — 10 fields, 1:1 with the DB columns. Eligibility predicates (`p0p1Slots.ts`) are
unaffected (they read `rarity`, `colors`, `typeLine`, `name`; all present). `collector_number` is
the canonical sort order; the view and `fetchP0P1Cards` both order by it (numeric-aware cast).

**Verify**: `seed_cards MSH` yields 256 cards (96 common / 100 uncommon / 60 rare); the picker
renders identically to the fixture; mock mode still works offline.

## Multi-contest viewing (fast-follow)

Implement when contest #2 lands (no user value with one contest); nothing in the backend blocks it.

The backend paths (`fetchP0P1PickStats(setCode)`, `fetchP0P1Cards(setCode)`, and
`public_p0p1_contests`) already support arbitrary historical sets. The frontend work:

- Add `/p0p1/:setCode` route mirroring `/leaderboard/:setCode` + `/tier-list/:setCode` (`App.tsx`);
  bare `/p0p1` redirects to the active contest's set.
- Mount **`TierSetDropdown`** fed from `useP0P1Contests()`. It collapses to a static label at ≤1
  contest (no visible change today). `onChange` → `navigate(/p0p1/${code})`.
- `useP0P1Ballot(setCode)` accepts the route param. `isPastDeadline` is derived from the selected
  contest's `voting_deadline`; voting UI shown only if `isActive && !isPastDeadline`.
- Results render via existing `PostVotingStats` / `CommunityGrid` (already read `pickStats` for an
  arbitrary `setCode`; no component changes needed).

## Local / dev testing

`public_p0p1_pick_stats` has no read gate, so there's no DB-side phase to flip and no risk of
leaking real picks — the aggregate is public by design, gated or not. The reveal/lock is a pure
frontend concern: to preview either phase, adjust the contest's `voting_deadline` in
`p0p1_contests` (config, not a security boundary) or just mock the client clock.

```sql
-- Move the deadline for local testing
UPDATE p0p1_contests SET voting_deadline = '2000-01-01T00:00:00Z' WHERE set_code = 'MSH';

-- Restore: re-run seed_p0p1_contests or UPDATE back to the bot/sets.py value.
```

## Verification

- `alembic upgrade head && alembic check` (model/migration drift) → `pytest bot/tests/`.
- Run `seed_p0p1_contests` + `seed_cards MSH`; confirm `public_p0p1_contests` and `public_cards`
  return rows via the Supabase SQL editor.
- Manual DB check: `public_p0p1_pick_stats` returns aggregates for complete entrants for any
  `set_code` regardless of deadline — no gate to verify, just confirm the view recreated cleanly.
- Frontend: page skeleton renders until `useP0P1Contest` resolves; countdown, set name, and lock
  all derive from the DB row; the community grid / `PostVotingStats` stay hidden until
  `isPastDeadline` (UX reveal, confirmed by toggling the deadline per above); mock mode still works
  offline; card picker contents match the fixture.

## Out of scope

- Server-side deadline enforcement, for either read or write. With the read gate gone, the voting
  deadline is now **entirely client-enforced** for both the reveal moment and the write/edit window
  (`upsertP0P1Pick` / `deleteAllP0P1Picks` stay unguarded). Acceptable because reads are public by
  design and there's nothing left to protect. If write-side abuse becomes a real concern, the
  optional RLS timestamp check already noted in `spec/p0p1-voting-mvp.md:111`
  (`current_timestamp < voting_deadline`) is the fast follow — flag only, not built here.
