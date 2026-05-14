# Pod Draft — Phase 1 Implementation Notes

Working doc for the `pod-draft-phase-1` branch. Read this together with `spec/pod-draft-spec-phase1.md` (the original brainstorm) — this file captures where the implementation diverged.

Branch is local-only and **not pushed to master**. All commit timestamps have been backdated to evening hours.

## Status at last checkpoint (commit `2bcbbe8`)

| Milestone | Status |
|---|---|
| 1 — Migration + models | ✅ |
| 2 — pod_drafts service layer | ✅ |
| 3 — sesh embed listener + parser | ✅ |
| 4 — PodDraftManager + T-5 reminder | ✅ |
| 5 — Ready check + /ready + auto-ready | ✅ |
| 6 — Bracket lifecycle + champion finalization | ✅ (rewritten as Python Swiss) |
| 7 — Read + admin commands + guest linking | ⏳ pending |
| 8 — Test suite (parser, bracket, scoring, linking) | partial (parser + swiss done) |

200 tests passing.

## Key divergences from the spec

### Bracket is Python Swiss, not Draftmancer's generateBracket

The spec assumed matches would be played inside Draftmancer (it has its own bracket UI). Reality: matches happen on MTG Arena, players just report results in Discord. We removed the entire `generateBracket('Swiss')` + `sessionOptions` diff pipeline and replaced it with:

- `bot/services/pod_swiss.py` — pure pairer + standings (no DB, no Discord). Tiebreakers follow MTR §1.6 (OMW% → GW% → OGW% → name), with the 1/3 floor.
- `bot/services/pod_tournament.py` — drives the post-draft Discord flow: one green embed per round listing all pairings, with N Discord Select dropdowns underneath (up to 5 → supports 10-player pods). Players submit results from the dropdown; the embed updates in place.

Result submission is **trust-based**: anyone can pick any result; results are editable (re-pick = overwrite). `/pod-result-edit` (admin) is still planned for correcting committed results post-round-advance.

### Identity matching — `Player.arena_name` (planned, milestone 7)

Same sesh URL is shared across all attendees (intentional — Yes/Maybe isn't a hard roster). Draftmancer userNames are user-chosen and rarely match Discord names cleanly. Plan:

- Add `arena_name` column to `players`.
- `/pod-link-arena <arena_name>` sets the invoker's `Player.arena_name` and backfills past unlinked participations.
- `/join` flow prompts for arena_name as a final step.
- Bot matches `sessionUsers.userName → Player.arena_name` first, then `discord_username`, then `display_name`. Misses become guests (player_id=NULL) and resolve later via `/pod-link-arena`.
- Standings post renders each linked participant as `[Name](dischord.pages.dev/leaderboard/<slug>)` markdown.

### `/pod-takeover` (mutiny, not in original spec)

Ported from Amelas/DraftBot. Transfers Draftmancer session ownership to the invoker and disconnects the bot. **Refuses while a draft is in progress** because Draftmancer's protocol silently rejects `setOwnerIsPlayer(True)` and `setSessionOwner(...)` while `drafting` is true if the owner is spectator-only. Works pre-draft and post-`endDraft`.

### Auto-ready check + Not-Ready cancel

When sessionUsers fills to `max(1, expected_attendee_count)`, the bot fires the ready check automatically. If anyone clicks "Not Ready" during the auto check, it cancels and the round falls back to manual `/ready`. Manual `/ready` is unconstrained (toggle Ready/NotReady all you want).

### Identity / counter changes

- `pod_draft_events.event_number` and `pod_draft_config` table removed in commit `d470ec1`. Event identity is now name + `event_date`. `draftmancer_session` is named `{prefix}-{set}-{#N|Month-D}` with `-A`/`-B`/`-C` letter suffixes for same-day collisions.
- Title-parsed `#N` is preferred for the session name when present; otherwise falls back to `Month-Day`.

### Test conveniences (env-gated, never in prod)

- `POD_DRAFT_SKIP_REMINDER_WAIT=true` — fire T-5 reminder 10s after detection instead of at event_time - 5min.
- `POD_DRAFT_BOTS=7` — pad seats so a solo human can `startDraft`.
- `POD_DRAFT_PICK_TIMER=1` — 1-second pick timer so the draft auto-resolves quickly.
- `POD_DRAFT_TEST_ROSTER=name1,name2,...` — override the post-`endDraft` roster used by `start_tournament` (and `!testbracket`). Accept any even count 2–10.
- `AUTO_REFRESH_ENABLED=false` — silences the 17lands auto-refresh tick on the test bot.

### Owner-only debug commands

- `!testbracket` (inside a pod-draft thread) — wipes that event's `pod_draft_matches` rows and re-runs the Python-Swiss flow using `POD_DRAFT_TEST_ROSTER`. Builds a `HollowManager` so `ACTIVE_POD_MANAGERS` lookups in `_maybe_advance` succeed.
- `!sync` — publish slash commands to the test guild.
- Currently no `!testsesh` (would mock a sesh embed pipeline); could add if needed.

## Architectural notes worth remembering

- **`ACTIVE_POD_MANAGERS` is in-memory only.** After a bot restart mid-bracket, dropdown clicks still commit to DB (persistent View dispatches), but `_maybe_advance` bails because no manager exists. We accept this and tell the user to re-run `!testbracket`. Could add reconstruction later if it bites in prod.
- **`RoundResultsView` is persistent.** `bot.add_view(RoundResultsView())` is called at startup, registering 5 generic Select slots with custom_ids `podmatchresult:0..4`. The match_id is encoded in each option value, so per-message state isn't tied to the registered View instance.
- **`HollowManager`** in `pod_tournament` is a manager-shaped stand-in used by `!testbracket` — no Draftmancer socket, just enough state (`bot`, `event_id`, `thread_id`, `tournament_players`, `current_round`, `finalized`) for the bracket flow to drive itself.

## Pending work (milestone 7 + 8)

### M7 — Read + admin commands + linking

1. Migration: add `players.arena_name` (nullable string).
2. `/pod-link-arena <arena_name>` — sets invoker's `Player.arena_name` (always-overwrite) and backfills past unlinked `pod_draft_participants` by `draftmancer_name`. Reply: "Linked N past events to your account."
3. `/join` flow update — add a final DM prompt asking for Arena name. Skip-able. Stores `arena_name` on the new Player row.
4. `pod_draft_participants` insert logic — prefer `Player.arena_name` match, then `discord_username`, then `display_name`. The auto-link in `_add_attendee` + `upsert_participant` both need updating.
5. `/pod-leaderboard [set:]` — champion history per set, plus a Cube/Special section by `format_label`.
6. `/pod-stats [player:]` — per-player career view (lifetime trophies, in-set trophies, events played, total record).
7. `/stats` augmentation — append "Pod trophies: 2 lifetime · 1 in SOS" line when the invoker has any pod-draft trophies.
8. `/pod-result-edit <event_id> <player_name> <field> <value>` — admin, fix placement/record/winner/score/eliminated_round.
9. `/pod-result-delete <event_id>` — admin, cascade-deletes the event row. Ephemeral confirmation prompt.
10. Standings post: render each linked participant as `[Name](dischord.pages.dev/leaderboard/<slug>)` markdown.

### M8 — Tests for remaining surfaces

- `/pod-link-arena` behaviors (sets arena_name, backfills, overwrites)
- `/join` arena_name capture
- Champion finalization writes correct standings (already covered indirectly via pod_swiss tests)
- Admin command validation paths

## Quick reference — test runbook

```bash
# Start the test bot (local dev)
docker start dischord-pg
.venv/bin/python -u -m bot.main

# Drive a fake bracket on an existing pod-draft thread:
# 1. Create or pick a sesh-detected thread in #pod-draft-coordination
# 2. Inside the thread, run:  !testbracket
# 3. Pick from each dropdown to advance through R1 → R2 → R3 → champion

# Full draft flow (real sesh + real Draftmancer):
# 1. Run sesh /create in #pod-draft-coordination
# 2. Bot detects, posts a confirmation in the auto-created thread
# 3. With POD_DRAFT_SKIP_REMINDER_WAIT=true, 10s later the bot connects to Draftmancer
# 4. Join the Draftmancer URL, /ready (or wait for auto-ready), click Ready
# 5. Draft completes (POD_DRAFT_PICK_TIMER=1 keeps it snappy)
# 6. endDraft triggers Python Swiss → R1 pairings post in the thread
```

## Reference

- Amelas/DraftBot is the canonical source for Draftmancer socket protocol patterns. See `services/draft_setup_manager.py`, `cogs/draft_control.py` (`/mutiny`).
- Draftmancer server source: https://github.com/Senryoku/Draftmancer/blob/main/src/server.ts — owner-only socket events are gated by `prepareSocketCallback(..., true)`.
