# Tier-list trend + history — handoff

_Last updated: 2026-06-11 (end of build session; PRs open)_

Feature spanning two repos: card-tier **trend arrows** (public) and **per-date history** (patron) on 17lands, consumed on the LLU site, plus a **grader-grades** popup on LLU.

## Repo state

### mtg-draft-logger (17lands) — both branches pushed, PRs open, NOT merged

- **PR #3364** `feature/tier-list-history` → `master`: the backend. Commits: `4a686b92` (original API) + `d3b328b0` (viewer-level patron access, trend baselines, history_days) + `59677182` (builders unit tests).
- **PR #3365** `feature/tier-list-history-ui` → `feature/tier-list-history` (stacked): the full tier-list page UI in one commit.
- `test/python/db/test_card_rating_history.py` is in a git stash on the 17lands repo (`stash: WIP on feature/test-suite`) — it needs the `feature/test-suite` harness (`support.*`, `frozen_time`, `make_tier_list`) and lands with that stack, ideally with a new test for `parse_requested_history_date` ordering.
- The committed builders tests need a reachable DB to collect (importing `db.data_model` connects); locally use `DATABASE_URL='mysql://seventeenlands_code:mypassword@127.0.0.1/seventeenlands' poetry run pytest test/python/data_model/`.

### DischordLeaderboard (LLU) — branch `dev`, frontend uncommitted, user reviews before commit

- `frontend/src/data/tierList.ts`, `frontend/src/components/TierGrid.tsx`, `TierFilterBar.tsx`, `constants.ts` — see `spec/tier-list-status.md` for the LLU-side feature state.
- Decision: the 17lands Trend dropdown is **not** being ported to LLU; LLU keeps its own single cycling trend toggle (all → ▲ → ▼ → off).

## Backend API contract (`/data/tier_list/<uuid>`, CORS-enabled)

Public (anonymous, no login):
- `ratings[].trend` — `up`/`down`/`null`, current grade vs the card's baseline.
- `ratings[].trend_from` — **always present** when the card has a baseline: the first grade it settled on, on a date before today. This IS the "set review grade". (Changed from earlier drafts where it existed only on trending cards.)
- `history_days` — count of calendar days (UTC) on which the list net-changed. Lets clients show "N past versions" without revealing contents.

Patron-only (any logged-in `patron_uncommon`+ **viewer** — ownership does not matter):
- `history` — one event per UTC day the list changed: `{date, cards_changed, changes:[{card_id, from_tier, to_tier, direction}]}`; `null` for everyone else.
- `?date=<YYYY-MM-DD | ISO timestamp>` — grid snapshot as of that moment, with trends recomputed as of that date. Bare dates mean end-of-day.

**LLU needs only the public fields.** The set-review-vs-current comparison is `trend_from` vs `tier` — no patron, no login, works through the LLU Pages Function proxy as-is.

## Key design decisions

- Trend/history aggregate by **calendar date** (UTC); the initial `TBD` and same-day churn are not movement. A card trends only if its current grade differs from its first settled grade from an earlier date.
- The 17lands UI merges adjacent history events that fall on the same **viewer-local day** client-side; labels use local dates. Server buckets stay UTC, so the public `history_days` count can differ by ±1 from a merged patron view (accepted for v1).
- Snapshot views are **read-only** in the editor (dragging while a past date is selected would autosave stale values over current ratings).
- LLU joins graders by **card name**, not `card_id` (local consensus fork uses different ids than 17lands prod).
- Grader review lists are **locked** → cached `staleTime/gcTime: Infinity`; consensus `staleTime: 1h`.

## Local dev / verify

- Local 17lands stack: docker (`mtg-draft-logger-*`), web on `:8008`, MariaDB on `127.0.0.1:3306`. Gunicorn and webpack both auto-reload on edit.
- Faked history in local MSH list `11bab60203f2410a94a41bb7981bae09`: created Jun 9, ~1/3 changed Jun 10, several live-test edits Jun 11 (including a UTC-Jun-12 bucket from a 21:30 ART session).
- Owner of that list is user 21518 (developer+moderator → patron_uncommon). To preview the non-patron upsell: `UPDATE user_roles SET ended_at = '2026-01-01' WHERE user_id = 21518;` (restore with `ended_at = NULL`).
- Grader lists (real 17lands): Alex `4806ce67270a4ea392fd1736bb8e708f`, Marc `a3c1255425a44f5b866a967f0a5b131e`.

## Open items

1. **Merge PRs #3364 → #3365** (rconroy review).
2. **db repository test + date-parse test** land with the `feature/test-suite` stack (test currently stashed in the 17lands repo).
3. **LLU frontend** still uncommitted on `dev` — commit when approved.
4. **Before MSH is public / LLU deploy**: delete the MSH fixture + its `TIER_LIST_DATA_BASE_OVERRIDES` entry in LLU (see tier-list-status.md).
5. Publicize the patron per-date feature once shipped — changelog draft was shared on Discord 2026-06-11.
