# Pod Draft Review — on-site draft recap (design)

**Status:** design agreed (unified artifact), build not started — see the **Handoff** at the bottom for current repo state and the next concrete steps. **Todoist:** "Draft Review on site" (`6gh4FGfH3C38Q6qj`). **Reference:** Draftsim recap (`https://draftsim.com/recap/?id=57ol2yMMR`) — pick-by-pick walkthrough with pack context.

## Goal

A web draft recap for pod drafts: for each seat, step through the draft pick by pick (P1P1 → P3P14), showing the pack as it was seen and the card that was taken. Navigable, per-seat. This is the on-site analogue of opening a MagicProTools log, but native, prettier, and tied to the pod page.

## Why decide the structure now

We're about to ship the deck view on a per-seat denormalized column (`mainboard_cards`). A draft review needs the *pick sequence*, not the final deck — different data, but derived from the **same source** we already store (`draft_log_gz`). Rather than accrete a second per-feature data path, this doc proposes deciding the data structure once so the deck view, the draft review, and a future pool view all derive from one artifact.

## What already exists

- **`pod_draft_events.draft_log_gz`** (compact, gzipped per event): a card table (`id, n, cn, s, r, c`), `packs` (each booster's contents), `picks` (per-seat pick indices), and `seats`. This is the full draft.
- **`draftmancer_log.simulate()`**: already reconstructs, from the compact log, exactly which cards each seat saw at every pick. The hard part of a recap is written — in Python — and needs porting to TS.
- **`mainboard_card_ids` / `mainboard_cards`** (per seat): the built 40, for the deck view.
- **Gaps in the compact log**: the card table dropped `cmc` and `type`, and the log carries no `decklist` (main/side). Those were captured separately into `mainboard_*`.

## Recommended structure: one canonical, client-consumable draft artifact

Expose the compact draft log per event and have the client reconstruct everything. Enrich the compact shape so it is self-sufficient:

- card table entries gain **`cmc`** and **`type`** (so the deck view can group by mana value / split lands client-side)
- add a per-seat **`decklist`**: `{ main: [cardId], side: [cardId] }` (so the built deck derives client-side)

With that, all three views derive from the single artifact:

- **Deck view** = `decklist.main` resolved against the card table (no `mainboard_cards` needed)
- **Draft review** = `packs` + `picks` via a TS port of `simulate()`
- **Pool view** (future) = all of a seat's `picks`

Consequence: **`mainboard_cards` and `mainboard_card_ids` become redundant** and can be dropped once the artifact lands.

## Exposure mechanics (decision needed)

- **Option A (recommended): store the compact log as uncompressed JSONB**, expose via a `public_pod_draft_log` view; PostgREST/CDN gzip compresses the response over the wire, so the client reads plain JSON with no decode step. Storage ≈ 50–100 KB/event uncompressed — negligible at pod scale.
- **Option B: keep `bytea` gzip**, expose it, client hex-decodes + `DecompressionStream('gzip')`. Smaller at rest, but adds client decode code and `bytea`-over-supabase friction.

Recommend A, and drop the `bytea` column in the same migration.

## Migration + backfill

- `build_compact` starts emitting `cmc`, `type`, and per-seat `decklist`.
- Migration: add the JSONB column + `public_pod_draft_log` view + grants (`anon` + `authenticated`, `to_regclass`-guarded per the prod-drift convention).
- Re-ingest the `logs/` files to populate; new pods populate going forward.

## Frontend

- TS port of `simulate()` (small, deterministic).
- Review surface: per-seat, pick-by-pick. Pack grid with the taken card highlighted, prev/next pick nav, seat switcher. Modal vs dedicated `/pods/<slug>/review/<seat>` route is an open call.
- Re-point the deck view to derive from the artifact.

## Phasing

- **Phase 0 (now):** decide the structure. If unified, decide the fate of the in-flight `mainboard_cards` work — ship it as a stopgap and migrate later, or revert it before it lands and build the deck view on the artifact from the start.
- **Phase 1:** enrich `build_compact`; store/expose the JSONB artifact; re-ingest; re-point the deck view; drop `mainboard_*`.
- **Phase 2:** build the pick-by-pick review UI.

## Open decisions

1. Unified artifact vs. keep `mainboard_cards` for the deck and design review separately. (Recommend unified.)
2. Exposure: uncompressed JSONB (A) vs. `bytea` gzip (B). (Recommend A.)
3. Drop `mainboard_cards` / `mainboard_card_ids` now, or after the artifact lands?
4. Review UI surface: modal vs. dedicated route.
5. Privacy: a recap exposes the full pick history (what each seat passed). Pods are always public per project rules, so this is presumed fine — confirm.

## Relationship to the sibling task

"Draft Review post-round-3 announcement" (`6ggR5mQFMwwGM7WC`) is the Discord-side companion: after round 3, the bot posts log links + the voice channel for whoever drives the review. On-site review is the web recap. Complementary — the announcement could later deep-link to the on-site recap.

---

## Handoff — 2026-06-14

Decisions locked this session: **go with the unified artifact**; the `mainboard_cards` deck-view approach is **abandoned**, and `mainboard_card_ids` is to be dropped too.

### Repo state right now

- **`master` (local, 1 commit ahead of `origin/master`, unpushed):** commit `e7ddddd` "Scroll the pod player panel's games under a fixed header" — a keeper, unrelated to this feature (fixed-height panel column, pinned seat header, match list as the only scroll region). The frontend deck-view is fully reverted from master; `tsc -b` clean, no `mainboard` refs in `frontend/src`.
- **Dead code already on `origin/master` (pushed) from commit `e26df58`** — must be removed by a forward change, NOT history surgery:
  - `pod_draft_participants.mainboard_cards` column + its exposure in the `public_pod_draft_event_participants` view (migration `m1n2o3p4q5r6`)
  - `resolve_mainboard()` in `bot/services/pod_draft_manager.py` and the `apply_mainboards` write to `mainboard_cards`
  - the pre-existing `mainboard_card_ids` column + its `apply_mainboards` write (slated to go too)
- **`pod-deck-view-wip` branch (commit `3fc5c65`):** preserves the reusable rendering — the stacked-pile deck modal (columns by mana value, Scryfall images via `set/cn`, `×N` badges, screenshot/cards tab toggle), the minimal resolved-card JSON shape, and the fixtures. **Cherry-pick the modal from here** when building the artifact deck view; do not merge the branch as-is.

### Next steps

1. **Cleanup migration (forward):** drop `mainboard_cards` and `mainboard_card_ids` from `pod_draft_participants`, remove `mainboard_cards` from the public view, delete `resolve_mainboard` + the `apply_mainboards` writes. Guard view grants with `to_regclass`. Check prod `alembic_version` vs master head first (m1n2o3p4q5r6 may be applied to prod) — see [[project_prod_migration_drift]].
2. **Enrich `build_compact`** (`bot/scripts/draftmancer_log.py`): add `cmc` and `type` to each card-table entry, and a per-seat `decklist` `{ main, side }`. Re-ingest the `logs/` files (`bot.scripts.ingest_pod_draft_log` / `/pod-backfill`).
3. **Expose the artifact:** store the compact log as JSONB (uncompressed) per event, `public_pod_draft_log` view + grants. (See "Exposure mechanics" above for the JSONB-vs-bytea call — JSONB recommended.)
4. **Frontend:** TS port of `simulate()`; pick-by-pick review UI; re-point the deck view to derive from the artifact, reusing the modal from `pod-deck-view-wip`.

### Resolved open decisions

- #1 unified artifact — **yes.**
- #3 drop `mainboard_cards` / `mainboard_card_ids` — **yes, drop both** (step 1 above).
- #2 (JSONB vs bytea) and #4 (modal vs route) and #5 (privacy) still open.
