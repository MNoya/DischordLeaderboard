# Pod Team-Draft vote

## Goal

Make Team Draft discoverable and let a small pod opt into it, without changing the default for full pods. The community defaults to 8-player Swiss (Fast Bracket as an optimization); Team Draft is the better shape for a 6-player pod. Rather than force it, the bot **offers** Team Draft to a settled small pod and the players **vote** it in.

Opt-in, never automatic: a pod stays on its current pairing mode unless the vote locks. A pod nobody converts just runs as Swiss/bracket.

## Model

- The offer is **its own embed card** posted to the thread, shaped like the `/pod-table` card: a green embed, the prompt as the title, an instruction line in the description, a `Votes (N)` field listing who has voted, and one primary vote button. It's a distinct message, not an edit to the lobby card — a call to action.
- The button is static **`🤝 Team Draft`** — no tally in the label, so rapid clicks don't churn it. A click toggles the clicker's vote; clicking again retracts. No Yes/No pair, no countdown.
- **The vote is public**: the `Votes (N)` field lists who's voting, so players see the push building and pile on.
- Locks at a **majority of the pod** — `pod_size // 2 + 1`, i.e. 4 of 6. The pod size is fixed when the offer is posted (`team_vote_size`), so a mid-vote arrival/leave can't move the target.
- **No strict electorate** — being on the draft is enough; a click isn't gated on current Draftmancer-session membership.
- **On lock (edit-to-locked):** switch the pod with `set_event_pairing_mode(event_id, "team")` and **edit the offer card in place** — title flips to `🤝 Team Draft is on!`, the instruction line drops away (the way pod-table drops its "once N join" line once the table opens), and the button is removed. The card stays as the record of the vote; there is no separate pairing-change notice.
- 6-player pods only in this version. 8 and 10 stay Swiss/bracket by default even though Team Draft supports them.

## When the offer appears

Only from explicit "this pod is settled small" signals — never on any lobby that transiently holds 6 while filling toward 8. (You can't collapse this to "6 present in Draftmancer": Maybe RSVPs can still trickle in and take a scheduled pod to 8, so 6-present isn't settled until the start time.)

1. **`/pod-table` overflow table.** The table is capped at its size, so 6 there really is 6 — but the offer still waits for **Draftmancer presence**: `materialize_table` *arms* it (`arm_team_vote_offer(len(claims))`), and it fires once that many players are actually in the Draftmancer lobby (checked in `_refresh_lobby_status` via `_maybe_offer_armed_team_vote`). Presence, not the Discord table claims, so the bodies are there to ready-check.
2. **Scheduled pod at its start time.** Wait until the scheduled `event_time` — by then the Maybes have shown or they haven't, so the count is settled. If the lobby is even and 4–6, post the offer. Trigger: a new at-`event_time` scheduler job (`schedule_team_vote_offer` / `fire_team_vote_offer` in `bot/tasks/pod_draft_reminder.py`), armed alongside the reminders in `SeshListener._schedule_reminder` and re-armed by `reschedule_pending_events`.

If the vote never reaches the majority, the offer **stays open** until the draft starts; the pod proceeds as Swiss/bracket. No expiry window. If the lobby grows past six, the offer is retired.

## Ready Check at lock

When the vote flips a pod to Team Draft, propose a Ready Check — the same nudge the full 8-player lobby gets, because a locked pod is committed to its size and ready to start. The precondition is bodies present: you can only ready-check players who are in Draftmancer, so the nudge keys off the pod's players being present ("6 locked in"), not the vote itself.

Status: **demonstrated in the preview**, not yet wired into the live lock path. The clean live version makes the existing lobby-full nudge (`_maybe_schedule_lobby_full_prompt`, hardcoded `_LOBBY_FULL_THRESHOLD = 8`) fire at the pod's **expected** size rather than a fixed 8, so a 6-pod prompts at 6 and an 8-pod still prompts at 8. Follow-up.

## Vote UI

- The button is a restart-safe `TeamVoteButton` DynamicItem keyed on the event id (`bot/services/pod_team_vote.py`), registered once via `bot.add_dynamic_items(TeamVoteButton)` in `bot/main.py`.
- The manager holds the offer message handle and the vote state: `team_vote_message`, `team_voters` (Discord id → display name, click-ordered), `team_vote_offered`, `team_vote_size`, guarded by `_team_vote_lock` so concurrent clicks serialize. Each click re-renders via `interaction.response.edit_message`.
- The offer is retired (deleted) at draft start and if the lobby grows past six — but on lock it's kept (edited to the locked state), not deleted.

### Copy

Everything lives in `bot/services/pod_team_vote.py` so the live card and the `!test` preview share one source: `TEAM_VOTE_PROMPT`, `TEAM_VOTE_GATHERING`, `TEAM_VOTE_LOCKED_TITLE`, `TEAM_VOTE_TALLY`, `TEAM_VOTE_EMOJI`, `TEAM_VOTE_BUTTON_LABEL`, `team_vote_needed`, `build_team_vote_offer_embed`.

- Title while gathering: `6️⃣ Players locked in! Make it a Team Draft?` — mirrors the 8-player `MSG_LOBBY_FULL_PROMPT`.
- Instruction (description): `Turns into a Team Draft once {needed} players vote.` — pod-table voice.
- Votes field: `Votes (N)` header + the voter names, comma-joined. Mirrors pod-table's `Players (N)`.
- Button: `🤝 Team Draft`, primary, static. The 🟩/🟦 squares stay reserved for the two teams.
- On lock: title `🤝 Team Draft is on!`, instruction dropped, button removed.

Exact wording reviewed visually, not asserted in tests.

## Preview

`!test teamvote` posts the offer card with a **working** 🤝 button and three votes prefilled, so the previewer's own click is the fourth — locking it to Team Draft (edit-to-locked) and posting the `6️⃣ Players locked in! Initiate Ready Check?` prompt. Self-contained, no live pod. The shared builders back it so it can't drift from the live card.

## Edge cases

- **A 7th player joins.** The lobby grew past six, so the offer is retired.
- **Vote reaches majority, then someone leaves.** Once locked it stays Team Draft; `set_event_pairing_mode` only locks out after `current_round > 0`, so a pre-draft lock is final.
- **Odd count at o'clock.** Team Draft needs even teams; the scheduled trigger only offers at an even count of 4–6.
- **Draft starts before the vote locks.** Whatever `pairing_mode` is set at `startDraft` wins; the unlocked offer is retired at draft start.

## Integration points

| Concern | Location |
|---|---|
| `/pod-table` trigger | `bot/commands/pod_table.py` (`materialize_table` → `arm_team_vote_offer`); fires on Draftmancer presence in `_maybe_offer_armed_team_vote` |
| Scheduled at-start trigger | `bot/tasks/pod_draft_reminder.py` (`schedule_team_vote_offer` / `fire_team_vote_offer`); armed in `bot/listeners/sesh_listener.py` |
| Button + view (restart-safe) | `TeamVoteButton` in `bot/services/pod_team_vote.py`; registered in `bot/main.py` |
| Offer state + lock | `PodDraftManager.offer_team_vote` / `toggle_team_vote` / `_lock_team_vote` / `_retire_team_vote_offer` (`bot/services/pod_draft_manager.py`) |
| Card + copy | `bot/services/pod_team_vote.py` (`build_team_vote_offer_embed`, constants) |
| Apply the switch | `set_event_pairing_mode(event_id, "team")` (`bot/services/pod_draft_manager.py`) |

## Out of scope (for now)

- Team Draft offers on 8/10 pods.
- A full pairing-mode poll (Swiss vs Bracket vs Team). This is a single binary opt-in toward Team only.
- Wiring the Ready-Check-at-lock into the live path (adaptive lobby-full threshold) — see "Ready Check at lock".
