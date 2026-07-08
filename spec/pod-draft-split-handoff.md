# Pod Draft split — Table 2 (handoff, WIP)

Owner-fired command that opens an additional draft table for a pod that filled up, with no sesh RSVP. Table 2 is a fully independent `PodDraftEvent` cloned from the source pod; it reuses the entire existing pod lifecycle (manager, socket, thread, tournament, standings, championship, trophies) because managers are keyed by `event_id`, so a second event row gets all of that for free.

Full design in `spec/pod-draft-split.md`. This file is the state-of-play for resuming.

## Status: working end to end on local, not yet deployed

Driven live via `!test split` against the local dev DB (real thread created, real Draftmancer lobby, real manager, real tournament path). Not yet `!sync`'d, so `/pod-split` is not published to Discord.

## Flow as built

1. Owner runs `/pod-split` in a pod thread (source inferred from the thread) or in `pod-draft-coordination` with an `event` param (autocomplete over recent events).
2. Bot posts a join card in the invocation channel: title = `<source> Table N`, description counts down ("Opens when 2 more join."), a `Joined (N)` field, and a primary "Join Table N" button.
3. Players click to join (toggle on/off). Claims live in memory on the view.
4. At `pod_split_open_threshold` (6) distinct joiners, the table materializes: clone the source into a `Table N` event, post an anchor message in the source thread's parent channel, open a thread off it, ping the joiners in (pulls them into the thread), then `start_manager(kind="tournament")`. The card title flips to `<source> Table N created` and the button becomes a link to the new thread.
5. From there it is an ordinary pod: the manager posts the live lobby card (Draftmancer link, roster), ready check at 6, seating, bracket-or-swiss, reporting, standings, championship.

## Key decisions (settled with the user)

- **Open at 6, not earlier.** `pod_split_open_threshold = 6` matches the draft minimum, so one number governs both "open the room" and "enough to draft". (Started at 4, bumped on request.)
- **No parity / min-size enforcement in the split flow.** The 6-threshold is the only bot-chosen number; drafting fires through the existing ready check. Odd/short rosters hit the normal tournament guards.
- **No DB link between tables.** Table 2 is standalone, related to Table 1 only by name (`<base> Table N`). `next_table_index` derives N by scanning sibling names, so a third split gives Table 3, and splitting from a Table bases on the original pod name.
- **Roster comes from Draftmancer, not RSVP.** The split manager is started with no `rsvps_yes`/`rsvps_maybe`, so the lobby card shows only `In Draftmancer` (+ `Unrecognized`), never `Waiting on` / `Maybe`. `lobby_embed.render` now skips those buckets when there are no RSVPs at all (general improvement, normal pods unaffected).
- **Claims are in-memory.** A mid-gather bot restart loses the claim list; owner re-runs `/pod-split`. Accepted by the user (bot does not restart during a session).
- **Trophies as normal.** Two tables = two independent pods = two winners.

## Files

New:
- `bot/commands/pod_split.py` — `Table2ClaimView`, `materialize_table2`, `build_split_view` (the single entry point the command and `!test split` both call), the `/pod-split` cog.
- `bot/tests/test_pod_split.py` — logic tests (table numbering, clone fields, third split).
- `spec/pod-draft-split.md`, `spec/pod-draft-split-handoff.md`.

Changed:
- `bot/services/pod_drafts.py` — `record_split_event`, `split_base_name`, `next_table_index`, `build_split_session`, `preview_split_target_sync`.
- `bot/config.py` — `pod_split_open_threshold = 6`.
- `bot/commands/messages.py` — `MSG_SPLIT_*` copy.
- `bot/commands/descriptions.py` — `POD_SPLIT`.
- `bot/main.py` — register the cog.
- `bot/services/lobby_embed.py` — gate Waiting/Maybe fields on presence of RSVPs.
- `bot/commands/testlobby.py` — `!test split` state (seeds a source pod, calls the real `build_split_view` preseeded to threshold-1 so one owner click opens it; purges the prior test family on re-run).

## No-drift seam

`!test split` reimplements nothing — it calls the production `build_split_view` / `materialize_table2` / claim view. Fixtures own only the seeded source event and the preseeded joiners. This is the constraint the user cares about most: change the flow and both the test and prod result move together.

## Open items before shipping

- **Command name.** `/pod-split` is a placeholder. Decide the final name before `!sync` (candidates: `/pod-table`, `/pod-open-table`).
- **`!sync` required** to publish the new slash command to Discord.
- **Spectators line.** The lobby card still shows `👀 Spectators` (Draftmancer sessionSpectators) on split tables. Left in as legit lobby state; the user may want it suppressed for split tables — open question, not yet decided.
- **Persistence.** If mid-gather restart resilience is ever wanted, the claim state would move to a "forming event" row (nullable thread/session + a persistent view + a small migration). Deliberately not done for v1.
- **Spec is WIP** — reflects the design as built, but predates any post-deploy learnings.

## How to test

```
# local dev DB, bot running via `dchord-bot watch`
!test split          # in any channel or thread; preseeded to 5, one click opens Table 2
```

Re-running `!test split` purges the prior test source pod and its tables (events, managers, created threads) first.
