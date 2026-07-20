# Second-table auto-offer

## Goal

When a scheduled pod fills and its draft fires, the players who signed up but didn't make the table of 8 shouldn't have to notice, re-count, and reorganize by hand. The bot already knows the 8 who got seated; it subtracts them from the pod's Yes/Maybe roster and offers the leftovers a ready-to-claim Table 2, so a second pod self-organizes off the same signup with no mod intervention.

This sits on top of `/pod-table` (`bot/commands/pod_table.py`), which already clones a pod into "Table N", posts a claim card with a 🪑 button and a threshold, and on materialize spins up the thread, Draftmancer lobby, and manager. The new work is a trigger and a leftover computation; the claim card, materialize flow, and lobby handoff are reused unchanged.

## Trigger

Fire once, when pod 1's draft actually starts — the moment the Draftmancer session locks its 8 in (the manager's draft-start path). Earlier moments are too fluid: people drift in and out of the lobby right up until the draft begins, so the "specific set of 8" isn't real until then. Only pods born from a scheduled RSVP card qualify, since they carry the signal roster to subtract from; queue- and poll-born pods have no standing roster and are skipped.

## Leftover computation

The source of truth is the pod's signal roster — everyone who RSVP'd Yes or Maybe. Subtract the locked 8 to get the leftovers, Yes ahead of Maybe. This is the same cut `_seating_pool` (`bot/commands/pod_draft.py`) already computes for the seeding table, where the *overflow* list is exactly the Yes RSVPs beyond the seated 8. Reuse it, extended to (a) carry each leftover's Discord user id, since the claim card pings and de-dups by id, and (b) append the Maybe roster after the Yes overflow.

Matching the locked 8 back to roster members: prefer the linked Discord member id where a seat was linked (manager `link_seat`), and fall back to casefolded name matching (arena/display), the way `_locked_table_names` already keys its dedup. Name-only matching is the fuzzy edge; a missed match just means someone appears on both the seated table and the leftover list, which the claim card already tolerates (a duplicate click is a no-op).

### Roster source: bot cards vs sesh

The trigger and the locked-8 detection are shared: both come from our Draftmancer manager, which runs the lobby regardless of how the pod was created. `_seating_pool` likewise already reads whichever roster exists — `fetch_sesh_rsvps` for a sesh-born pod, the signal roster for a bot-card pod — so the overflow cut computes either way. The difference is identity: bot cards store each signup's Discord user id, giving exact `@mention` pings and clean id-based dedup, while sesh only exposes display names scraped from its embed, so leftover pings on a sesh pod are best-effort name→member resolution and some won't resolve. Since the bot card replaces sesh, treat bot-card pods as the real design and sesh as a degraded, transitional path.

## Offer

Auto-post a Table 2 claim card in the pod's parent channel — beside Table 1, the placement `/pod-table` resolves to today — pinging the leftovers. This reuses `build_table_view` → `TableClaimView` → `materialize_table` wholesale: threshold reached → clone the source pod → new thread + Draftmancer lobby → ordinary tournament manager.

Offer only when the leftovers (Yes + Maybe) number at least 6 — a full team-draft's worth, and the same count a table needs to materialize (`pod_table_open_threshold`), so the card's stated open-count and the trigger line up. Below 6, stay quiet and let the multi-pod notice on the RSVP card (`MULTIPOD_NOTICE`) carry the invitation on its own.

## Confirm — invited, not drafted

Leftovers are invited, not auto-seated. The card pings them and shows them as invited, but each must click 🪑 to take a seat. They RSVP'd Yes once already, but a fresh click confirms they're still around, so the second table never materializes on ghosts who logged off after the first pod filled. This is deliberately *not* the `preseeded_claims` path on `TableClaimView`, which pre-counts a claim toward the threshold — that is the opt-out model we rejected.

## Command access

`/pod-table` opens to everyone: drop the owner-only gate in `bot/commands/pod_table.py`. This matches the multi-pod notice, which already tells any player to run the command, and makes the auto-offer a convenience layer on top of a command players can fire themselves.

## Open items

- **Invited-list display.** Showing invited-but-unclaimed names on the card, distinct from claimed seats, needs a small `TableClaimView` extension. The minimum viable version pings the leftovers and shows claims as they accumulate, without a separate invited column.
- **Third pod.** 17+ signups would want a Table 3. It falls out naturally if the same trigger runs when Table 2's draft starts, but the leftover computation then has to subtract the seated sets of *every* live table off the signup, not just pod 1's. Out of scope for v1 (one offer, at pod-1 start); noted for later.
- **Signal linkage.** A Table N event is cloned via `record_table_event` and isn't tied back to the originating signal, so multi-table leftover math depends on collecting seated sets from the live managers rather than a stored link. Fine for the single-offer v1.
