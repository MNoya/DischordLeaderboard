# Pod format work — plan and state

Steps 0 and 1 are built, verified in the test server, and committing now. Next session: build step 2.

## What happens in prod today

A launcher slot fires at 6 signups into a latest-set pod. If people want an old set instead, they argue it out in the thread or pod chat, and the losers of the argument either skip the night or open a second table by hand with `/draft`. It works every day, but the demand is invisible until an hour before start, and that is where the tension comes from.

Two days of prod data (Jul 19-20) that shaped the plan: seven tables, four different old sets (NEO, KHM, DSK, FIN), and the old-set tables were half the seats. On Jul 19 both main pods were old sets and MSH was the overflow table; on Jul 20 MSH fired first and a FIN second table filled all 8. Old-set demand is not fringe, it is set-specific ("not my set, not playing" is common), and the second-table pattern is how the community already solves it.

So the system is not broken, it is blind. The plan: make the demand visible first, then tell people which set can actually happen, then give them one button to make it happen. Rebuild the pipeline only if that is still not enough.

## Decisions that are settled

- No format voting with a target. The old design (poll in the fired pod, format locks when 8 vote, confirm card) is dead and deleted; a full pre-deletion copy sits in gitignored `backups/pod-format-consensus-2026-07-21/`. Nobody is moved onto a format after committing.
- "Flashback" is a category, not a format. Counting happens per concrete set. A player's ranked list (`Player.flashback_ranking`) says which sets they would actually play.
- Latest fires first, old-set tables form second. That is the prod-proven order. Changing the order is step 3 territory, decided later by data. Launcher copy deliberately never states the firing order so it can change without a copy sweep.
- Flexible is only ever explicit: the picker's Any Format option stores both interests. An empty preference reads as "unstated" everywhere and rides with Latest on rosters while contributing nothing to flashback demand.

## What shipped in steps 0-1

- **Format Preference picker** (`InterestPromptView` in `bot/tasks/pod_daily_poll.py`): single-choice Any Format / Latest Set Only / Flashback Only, a ranked-sets modal behind Flashback (order = rank, stored on `Player.flashback_ranking`), Confirm-Pod buttons that save and join through the shared join path. Opens from the launcher button and from the grant card's Format Preference button (`register_format_preference_opener` in `bot/services/ping_roles.py`, launcher resolved via `pod_launch.latest_launcher_sync`).
- **Launcher team blocks** (`_roster_lines`): every roster groups under Latest Set / Flashback headers with counts; flexible players carry the `fi.FLEXIBLE_MARKER` glyph and land at the bottom of the team they fill (a byproduct of `format_teams`' two-pass distribution, not an explicit rule). A committed pod's thread link sits above the team block that matches its set.
- **The in-thread tally** (`bot/services/pod_format_poll.py`): posts when a fired pod's roster has flashback demand (`should_offer_format_poll`), pre-seeded with one vote per set on each present player's ranked list (`_seed_votes_from_rankings` in `pod_draft_manager.py`). Multiple choice, write-ins, adjustable; it decides nothing and locks nothing. Rank order only affects option insertion at the 20-option cap, never vote weight.
- **Preference snapshots on every join path**: launcher toggle, carry-over, and direct RSVP on a scheduled card (`set_rsvp`) all seed `PodSignalMember.format_interest` from the standing preference; a picker Save rewrites the snapshot across all of the day's launcher signals including reflected scheduled pods, so the board can't go stale within the day.
- **Join feedback**: launcher slot clicks answer with RSVP-style ephemerals (added green with start time, removed red). A click that also freshly grants a role folds the confirmation into the grant card (`card_lead` through `announce_pod_grant`) so no click produces two messages; the same combining covers Yes on the RSVP card.
- **Grant card additions** (`build_grant_view`): linked players see their preference and ranked sets plus a Format Preference button; unlinked players keep the Link Arena flow and no picker button.
- Shared vocabulary lives in `bot/services/pod_format_interest.py` (labels, markers, `preference_display`, `ranking_display`, `format_teams`, `composition`); shared copy in `bot/commands/messages.py`.

### Verifying in a test server

`!test reset` (also strips your slot roles so grant cards re-fire) then: `!test poll` for the launcher + picker + slot feedback; `!test launcher` for the committed-pod reflection and the RSVP-path snapshot seeding; `!test formatpoll` for the tally card; `!test welcome` for static grant/welcome card previews.

## Step 2 — one button for the second table (next)

When the tally shows a concrete set with a table's worth of support, the bot offers that set's table in the thread. The mechanic is the existing invite-not-seat second-table flow (`offer_second_table` / `build_table_view` in `bot/commands/pod_table.py`), made format-aware — not a fresh `/draft` queue. `/pod-table` grows an optional format argument and the offered table comes preset to the supported set.

- **Timing is a hard requirement from Jul 21 testing: the offer must run in parallel with the main pod's pre-start window.** Waiting until table 1 is drafting makes people anxious. Post while both tables gather, re-evaluate as tally votes change, retire at draft start like the other offers.
- The candidate pool is the whole gathered crowd, not just leftovers: a supporter may sit on the main roster and prefer the second table's seat — the pre-start window is exactly when they choose. `format_teams` / `fills_latest` is the balancing brain, fed by tally votes instead of standing interests; Any-Flashback voters balance the thinner side.
- Cannibalization gates everything: only offer when the partition leaves both tables at the fire threshold, and decide during the build what happens when claims later starve table 1 below it.
- Decided at build time: the exact support threshold, re-offer cadence as votes change, and whether an under-threshold second table keeps recruiting from the channel like Jul 20's FIN table did.

## Step 3 — parked, do not build yet

The bigger redesign stays on ice until steps 0-2 have run in prod for a few weeks: the anchor card that gathers players before anything fires, neutral thread names that gain a set code when a table locks, the per-set live count an hour before start, the press-to-claim-your-seat ready check, reposting cards that get buried in long threads (edit in place for small updates, delete-and-repost on phase changes or after enough chatter). The interactive mockup survives as `!test gather <scenario>` (`bot/commands/testpolls.py` + `bot/services/pod_gathering.py`, preview-only, no signals). One hard-won UI rule to keep: a thread shows its parent message's buttons as inert, so every phase players interact with needs buttons on a message inside the surface they are looking at.

If the saved preferences eventually show that latest-first ordering itself is the problem (Jul 19 suggests it sometimes is), that is the signal to come back here.

## Deploy notes

- Migrations `f1a2b3c4d5e6` (format_interests) and `b2c3d4e5f6a7` (flashback_ranking) must run on deploy (`alembic upgrade head`).
- No `!sync` needed — no slash command schema changed; everything is prefix commands, buttons, and embeds.
- The picker's set-symbol emoji need a bot restart after emoji re-uploads (`emojis.load()` runs once at startup).
