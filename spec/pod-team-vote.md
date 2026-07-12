# Pod Team-Draft vote

## Goal

Make Team Draft discoverable and let a small pod opt into it, without changing the default for full pods. The community defaults to 8-player Swiss (Fast Bracket as an optimization); Team Draft is the better shape for a 6-player pod. Rather than force it, the bot **offers** Team Draft to a settled 6-player lobby and the players **vote** it in.

Opt-in, never automatic: a pod stays on its current pairing mode unless the vote locks. A pod nobody converts just runs as Swiss/bracket.

## Model

- The offer is **its own embed card** posted to the thread — styled like the `/pod-table` card: a green embed with the prompt as the title, the current voters as the body, and one primary **tally button**. Not a silent edit to the lobby card; it reads as a call to action. A player clicks to vote, clicks again to retract. No Yes/No pair, no countdown.
- Locks when **4 of the 6** players vote yes — majority of the roster, `len(players)//2 + 1`. Non-voters count as no.
- **The vote is public**: the card lists who is voting for Team Draft up front, not just a count, so players can see the push building and pile on.
- **No strict electorate enforcement** — being on the draft is enough. Don't gate a click on current Draftmancer-session membership; if someone's part of the pod, their vote counts. `manager.player_session_users()` is still the count used for the `//2 + 1` threshold.
- On lock: `set_event_pairing_mode(event_id, "team")` (persists + re-renders the card) and a public thread notice via the existing `pairing_change_message` / `send_settings_notice` path. The lobby card already swaps to the team roster once teams are assigned at draft start.
- 6-player pods only in this version. 8 and 10 stay Swiss/bracket by default even though Team Draft supports them.

## When the offer appears

Only from explicit "this pod is settled at 6" signals — never on any lobby that transiently holds 6 while filling toward 8.

1. **`/pod-table` overflow table of 6.** The roster is explicit at creation, so post the offer as soon as the new table's lobby is live. Trigger point: `materialize_table()` in `bot/commands/pod_table.py:65-97`, where `start_manager(...)` establishes the new manager with `expected_attendee_count = len(claims)`. Offer when `len(claims) == 6` (the `pod_table_open_threshold` default, `bot/config.py:49`).
2. **Scheduled pod at its start time with ≤6 in the lobby.** Wait until the scheduled `event_time` — the clock is the signal that the pod is not filling further. If ≤6 real players are in the lobby then, post the offer.

If the vote never reaches 4, the offer **stays open and clickable** until the draft starts; the pod proceeds as Swiss/bracket. No expiry window.

## Scheduled at-start hook (new)

No callback fires at `event_time` today — every scheduled job runs before start (`fire_reminder` at T-10, `fire_roster_reminder` at T-60, underfill checks). Add an at-start job:

- Arm `scheduler.add_job(..., run_date=event_time, ...)` alongside the T-10 arm in `SeshListener._schedule_reminder` (`bot/listeners/sesh_listener.py:296-305`) and mirror it in the startup re-arm sweep `reschedule_pending_events` (`sesh_listener.py:408-417`).
- New fire callback modeled on `fire_roster_reminder` (`bot/tasks/pod_draft_reminder.py:140-177`): look up the manager in `ACTIVE_POD_MANAGERS` (it exists by then — started at T-10), read `len(manager.player_session_users())`, and post the offer when `<= 6` and the pod is not already Team mode.

## Vote UI

- The offer is a **standalone thread message** carrying its own persistent view with a single vote button (stable `custom_id` so it survives restarts, registered at `bot/main.py:230` via `bot.add_view(...)`). It is posted once per pod when the offer condition is met, edited in place as votes come in.
- The label carries the live tally `🤝 Team Draft (N/4)`; the button is present only while the pod is a 6-player offer candidate and not already Team mode.
- The manager holds the offer message handle (like `_lobby_full_prompt_message`) so the tally edit and the retract-on-roster-change can find it. Vote state (who has voted) is tracked on the manager, keyed by Draftmancer/Discord identity, and the message is retired if the roster leaves the offer condition.

### Copy

- Embed title (the prompt): `6️⃣ Players locked in! Make it a Team Draft?` — mirrors the 8-player `MSG_LOBBY_FULL_PROMPT` prompt.
- Button label: `🤝 Team Draft (N/4)`, primary style. The 🟩/🟦 squares stay reserved for the two teams; the vote button reads as "team up."
- Embed body, updated on each click: bare player names, `Ava, Bram, Cara` — no label, the title above is context enough. Empty until the first vote.
- On lock, reuse `pairing_change_message(actor, "team")` for the thread notice (actor = "vote").

Copy and the card build live in `bot/services/pod_team_vote.py` (`TEAM_VOTE_PROMPT`, `TEAM_VOTE_EMOJI`, `team_vote_needed`, `team_vote_button_label`, `build_team_vote_offer_embed`) so the live message and the preview share one source. The message is `thread.send(embed=build_team_vote_offer_embed(voters), view=<vote button>)`, styled like the `/pod-table` card. Exact wording reviewed visually, not asserted in tests.

## Preview

`!test teamvote` posts the untouched six-player lobby card followed by the offer as its own embed card — prompt title, two sample voters, and the inert 🤝 tally button at 2/4 — for iterating on the copy without a live pod. The shared builders above back it, so it can't drift from the eventual live message.

## Edge cases

- **Roster changes after the offer.** If a 7th player joins (heading to 8), retract the offer and drop the vote — the 6-player condition no longer holds. If someone leaves and the count stays even at 6, keep the offer. Re-evaluate on each lobby refresh.
- **Vote reaches 4, then someone leaves.** Once locked, it stays Team Draft; `set_event_pairing_mode` is locked out only after `current_round > 0`, so a pre-draft lock is final for the lobby.
- **Odd count (5) at o'clock.** Team Draft needs even teams; only offer at an even count. At ≤6 with an odd roster, skip the offer.
- **Ready-check races the vote.** Whatever `pairing_mode` is set at `startDraft` wins. The vote and ready-check coexist; if the draft starts before the vote locks, it runs Swiss/bracket.

## Integration points (summary)

| Concern | Location |
|---|---|
| New-table trigger | `bot/commands/pod_table.py:65-97` (`materialize_table`) |
| Scheduled at-start trigger (new) | `bot/listeners/sesh_listener.py:296-305`, `:408-417`; new callback in `bot/tasks/pod_draft_reminder.py` |
| Offer message + vote button/view | new persistent view (model on `LobbyReadyButtonView`, `bot/services/lobby_embed.py:38-84`); register at `bot/main.py:230` |
| Post/edit the offer message | manager, modeled on `_maybe_schedule_lobby_full_prompt` / `_lobby_full_prompt_message` (`bot/services/pod_draft_manager.py`) |
| Card + copy | `bot/services/pod_team_vote.py` (`build_team_vote_offer_embed`, `team_vote_button_label`, `TEAM_VOTE_EMOJI`, `team_vote_needed`) |
| Apply the switch | `set_event_pairing_mode(event_id, "team")` — `bot/services/pod_draft_manager.py:1729-1742` |
| Announce | `pairing_change_message` (`bot/services/pod_pairing_select.py:30-34`) + `send_settings_notice` |
| Threshold count (not enforced per-voter) | `manager.player_session_users()` — `bot/services/pod_draft_manager.py:624-631` |

## Out of scope (for now)

- Team Draft offers on 8/10 pods.
- A full pairing-mode poll (Swiss vs Bracket vs Team). This is a single binary opt-in toward Team only.
- Any change to how full 8-player pods default or ready-check.
