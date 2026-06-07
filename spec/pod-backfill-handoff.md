# /pod-backfill — thread-driven event reconstruction (handoff)

Build an admin command that reconstructs a complete pod-draft event from its Discord thread: the bot
reads every message, infers the event structure (participants, records, decks, matches, replays),
asks the invoker to confirm what it inferred and fill what it couldn't, then writes it all.

Origin: Peasant Cube '26 Draft 5 (2026-06-06) ran on the main Draftmancer site while the bot
listened on beta and recorded nothing. The event was reconstructed by hand across one long session —
bracket screenshots, the deck thread, a DraftLog .txt, and 17lands fetches. Every step below was
exercised manually that day; the command automates the same pipeline.

## Command shape

`/pod-backfill` — `[Admin]` gated like `/pod-champion` (`bot.is_owner` + `MSG_ADMIN_ONLY` from
`bot/commands/messages.py`). Invoked **inside the pod thread** (resolve event via
`load_event_id_by_thread_sync`); fall back to an `event` autocomplete param like `/pod-champion`'s.

Pipeline: **scrape → infer → confirm → write → post-process**.

## Reuse, don't rebuild

| Piece | Role |
|---|---|
| `pod_drafts.upsert_participant` | Find-or-create participants, resolves `player_id` via `_player_for_name` (arena alias → prefix → display/username → token) |
| `pod_backfill.apply_seat` | Per-seat placement/record/colors/caption/screenshot; `normalize_colors` (WUBRG, lower=splash), `strip_cdn_dims` |
| `pod_drafts.record_match` | Idempotent on (event, round, names) |
| `bot/scripts/ingest_pod_draft_log.py` | DraftLog .txt → `draft_log_gz`, seat indexes, mainboards, arena_name repairs, MPT submission per seat |
| `bot/scripts/backfill_pod_replays.py` | 17lands replays per token-holder; round attribution is **window-only** off `match.reported_at` |
| `pod_screenshots` listener | Live deck-capture conventions: caption with a record pattern locks the slot |
| `pod_swiss.standings` | Placement ordering (wins → OMW% → GW% → OGW%) once matches exist |

## What the thread yields (extraction layer)

- **Parent sesh message** (`sesh_message_id` on the event): Yes/Maybe attendee names.
- **Deck posts**: image attachment + caption → screenshot URL, caption verbatim, record via the
  existing record regex. Crucially the **poster's Discord id is ground truth** for identity —
  `message.author.id → Player.discord_id` beats every name-matching tier. (The manual run only had
  names; "C. Elegans = maimslap#64991" needed a human. The command gets it for free.)
- **DraftLog .txt attachment**, if posted → feeds the ingest path, which also yields the canonical
  Draftmancer userNames per seat.
- **Not extractable**: bracket screenshots (images, no OCR). Match pairings/scores come from replay
  inference (below) or from the confirmation step.

## Inference layer

- **Records** from deck captions ("2-1 rakdos stuff" → `2-1`).
- **Pairings + game scores from 17lands replays**: for token-holders, fetch `user_game_list`,
  filter to event day + `DirectGameTournamentLimited`, cluster games into matches, and mirror-join
  across players (timestamp ±2 min, same turn count, opposite result — the frontend H2H join logic,
  needed backend-side). In the manual run this **confirmed all derivable pairings and corrected two
  bracket scores** the players had misreported (3-game sets recorded as 2-0).
- **Round boundaries**: per-player game clusters give each match's real end time → drives
  `reported_at` (see invariants).
- **Placements**: champion = trophy-match winner; the rest via `pod_swiss` tiebreakers once matches
  are in. Surface the computed ordering for confirmation rather than asking for 8 numbers.

## Confirmation UX

Present the full inferred structure (one embed: seats, records, placements, colors, match grid) with
the **gaps explicitly flagged** — unmatched players, missing colors, unpaired rounds, unknown game
scores. Buttons/modals fill each gap; a final summary → **Confirm** button performs all writes in one
transaction. Include a "quiet vs announce" choice: stamping `championship_posted_at` suppresses the
startup announcement sweep (`reconcile_unannounced_championships`); leaving it null with matches
present makes the next restart post the champion embed.

## Data invariants (each one bit someone on 2026-06-06)

1. **Always set `draftmancer_name` = the Draftmancer userName** on participants. Match rows
   reference players by that string (no FKs). The frontend historically joined matches↔seats by
   `display_name` (works only because live flow sets both to the userName); the root fix — view
   migration `v9w0x1y2z3a4` exposing `draftmancer_name` + frontend `podSeatName()` join — may or may
   not be fully deployed when you read this. Check, and until the frontend half is live, also keep
   `display_name` = userName.
2. **`match.reported_at` must be realistic per-match times**, not insert time — replay round
   attribution windows derive from it. Set each to ~3 min after the match's last known game; estimate
   for matches with no token-holder.
3. Finalize = `socket_status="complete"`, `current_round=3`, `finalized_at` set.
4. Scoring needs nothing recomputed — pod points derive live from `record` + `placement`
   (trophy = `3-0` OR placement 1; `2-1` = 2 pts).
5. **17lands `user_game_list` only holds the last ~100 games** — replay backfill loses data if it
   waits days. The command should run it in the same pass.
6. Discord CDN attachment URLs carry expiring auth params; storing them matches live behavior, but
   prefer re-reading from the thread (fresh URLs) over copy-pasted ones.
7. The event row likely **already exists** (sesh listener creates it at RSVP time, possibly with zero
   participants — that's exactly the failure mode this command serves).

## Worked example (manual run to replicate)

1. Participants + seats: one-off script calling `upsert_participant` + `apply_seat` per seat
   (pattern preserved in the session's `backfill_peasant26_d5.py`, intentionally uncommitted).
2. Matches: `record_match` × 12 with bracket scores; later corrected two scores from replay data.
3. `reported_at` per match from 17lands game clusters.
4. `python -m bot.scripts.ingest_pod_draft_log <event_id> <DraftLog.txt>` → log, seats, mainboards,
   MPT links (8/8).
5. `python -m bot.scripts.backfill_pod_replays <event_id>` → 27 replays, all rounds attributed.

## Suggested build order

1. **Extraction service** (`bot/services/pod_thread_backfill.py` or similar) — pure functions over
   message dicts; table-driven tests on fixture threads.
2. **Replay-pairing inference** — backend port of the H2H mirror-join; pure, heavily testable.
3. **Wizard command** — gaps-first confirmation flow.
4. **Writers** — thin orchestration over the reuse table above; one commit, idempotent re-runs.

## Open questions

- Single wizard or staged subcommands (`/pod-backfill scan` → `/pod-backfill apply`)?
- Partially-recorded events (bot crashed mid-event, some matches exist): merge or refuse?
- Bracket data with no replay coverage and no user knowledge — accept placeholder scores (manual run
  used 2-0) or store unplayed-score sentinel?
