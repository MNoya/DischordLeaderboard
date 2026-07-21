# Pod nudge & reminder — implementation handoff

Kickoff for the next session. Read this, then `spec/pod-nudge-schedule.md`. The design is locked; this is the build plan, not a discussion.

## Status

- **Design: locked.** Full model in `spec/pod-nudge-schedule.md`. Championship automation in `spec/pod-draft-championship.md` (the "Automation (supersedes the manual Sesh flow)" section).
- **Shipped this session** — commit `ee5456ef` on `master`, not pushed: removed the `/pod-schedule` command; the bot now auto-posts the weekly schedule at noon Monday (owner DM + Post/I've-got-it/Skip buttons gone). Needs `!sync` on deploy to drop the slash command.
- **Already clean + committed (prior session):** the Scheduled underfill nudge copy and the launcher poll-nudge copy.
- **Uncommitted, leave for the user:** the spec files are design docs, uncommitted by choice. Unrelated user WIP is also in the tree (`roles.py`, `pod_team_vote.py`, `pod_draft_manager.py`, `spec/pod-format-poll.md`) — not part of this work, do not touch.

## Locked decisions (do not re-litigate)

- **Three pod types:** Scheduled (advance RSVP card), Launcher (same-day slot that fires into a card at the floor), Queue (on-demand, DraftBot count-based, out of scope for time-anchoring).
- **Two numbers:** floor 6 (min to run), aim 8. Scheduled aims 8 the whole way; Launcher aims 6 to fire, then 8 to fill. State at/above aim is **"ready", never "full"** — a 9th is welcome up to the Max Players cap, overflow spills to a second table.
- **One living nudge per pod, deleted ONLY on fire or window-close, never on a player count.** An 8→7 drop flips text back to "looking for 1 more" instead of vanishing. It **resends** (delete + repost to channel bottom) at attention moments to beat chat burial; silent edits between.
- **Rally is time-anchored, never fired far from the draft time:** T-3h **silent** reminder (T-2h catch-up) for any short pod; T-1h **@slot ping only when close** (needs ≤ 2). Drop the old one-short-only gate and the T-24h post.
- **Launcher fire within 3h** of the draft time → numberless **creation announcement** + @slot (the card's roster sells "almost full", the text carries no count so it can't go stale). Firing **earlier** → post the card silently, the underfill schedule recruits near game time.
- **No ping on reaching ready.** No-show handling is out of scope (a ✅ Yes is taken as coming).
- **Block non-admin `/draft` scheduling onto an occupied slot** — including an open launcher slot that already has sign-ups, not just created events. Admin (owner) overrides.

## Build order

1. **Scheduled path** — DONE (shipped). `bot/tasks/pod_underfill.py` + `build_underfill_message` in `bot/services/pod_schedule.py`: living message that clears only on lobby open (new `clear_underfill_nudge`, called from `open_ondemand_lobby` and `fire_reminder` via `register_underfill_clear` to dodge the import cycle), READY line past the aim, checks now `3,2,1` (T-3 silent, T-2 catch-up for short-notice pods, T-1 resurface + ping), T-1 pings any close pod (`pod_underfill_ping_close_gap = 2`, replacing the dropped `pod_underfill_ping_one_short_only`). Catch-up now inherits the most recent missed beat's offset so a caught-up T-1 can still ping. Tests updated; full pod suite green.
2. **Launcher convergence** — DONE (uncommitted). `_maybe_nudge_slot` and its count trigger are gone; unfired launcher slots run the shared beats via `fire_slot_underfill` (`bot/tasks/pod_underfill.py`), aiming at the fire threshold, living-nudge in pod-draft-chat linked to the launcher and disambiguated by pod name (slots share one launcher URL). Live joins/leaves edit it in place; it clears on fire (`_launch_slot`) and on expiry (`fire_slot_expiry`, plus the startup sweep). An empty slot stays silent — no signups means no pod-in-waiting to rally around. Fire ping gated by proximity: within `max(POD_UNDERFILL_CHECK_HOURS)` the card carries the numberless `POLL_FIRE_ANNOUNCE` @slot line, earlier fires post silently. `pod_signals.nudged_at` split into `one_more_pinged_at` (queue) + `last_call_pinged_at` (T-1 rally, claimed for scheduled and slot pods alike) — migration `d5e6f7a8c1b2`. `_nudge_ping_role` now resolves off the daily poll buckets (`slot_role_name_for_event_time`), so launcher-born cards ping at T-1 too; `slot_for_event_time` and `pod_nudge_in_chat` removed as dead. **← NEXT: step 3**
3. **Copy cleanup:** `QUEUE_NUDGE` (`bot/commands/pod_queue.py`) and `MSG_SECOND_TABLE_OFFER` (`bot/commands/messages.py`) → plain, drop the ⚡/🔥.
4. **Championship automation** (`spec/pod-draft-championship.md` Automation section): a dated auto-create off `championship_date` (mirror the weekly card jobs) plus the auto-announcement. Open design bits remain — plan before building.
5. **HOB `championship_date`** = Aug 1, 2026, ~2–3 PM ET in `UPCOMING_RELEASES` (`bot/services/pod_schedule.py:139`). One-liner; drives the final-week blurb and the championship auto-create.

## Key files

- Scheduled nudge: `bot/tasks/pod_underfill.py`, `bot/services/pod_schedule.py` (`build_underfill_message`)
- Launcher: `bot/tasks/pod_daily_poll.py` (`_maybe_nudge_slot`, `build_poll_nudge`, `_launch_slot`)
- Queue: `bot/commands/pod_queue.py` (`QUEUE_NUDGE`, `_maybe_nudge`)
- Get-ready reminders (unchanged by this work): `bot/tasks/pod_draft_reminder.py`
- Ping claim model: `bot/services/pod_launch.py` (`claim_nudge_sync`), `bot/models.py` (`PodSignal.nudged_at`)
- Championship: `bot/services/pod_drafts.py` (`is_championship`), `bot/commands/pod_draft.py` (seeding), `bot/services/pod_registration_embed.py` (crown embed), `bot/tasks/set_awards_post.py` (the separate Set Awards ceremony, already self-scheduling for the MSH→HOB rotation)

## Conventions

Plain declarative copy; no copy strings in specs; test logic not framework; hold commits until asked; never push; `!sync` after any slash-command change.
