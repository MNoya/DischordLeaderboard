# Pod Draft Scheduler — organizer automation

Automates the weekly pod-draft organizing loop the owner currently runs by hand: posting the schedule,
creating the Sesh events, and chasing RSVPs when a pod is short. Three features on the existing
`bot.pod_scheduler` (APScheduler) instance — the first two driven by one hardcoded slot table, the third
by the sesh-created events the bot already tracks.

## Current state

- The owner manually posts the weekly schedule, runs Sesh's `/create` for each event, and watches each
  sesh thread, pinging the channel when fewer than 8 people have RSVP'd Yes.
- The bot already detects sesh-created events (`bot/listeners/sesh_listener.py`), persists them as
  `PodDraftEvent` rows (`sesh_message_id`, `discord_thread_id`, `event_time`), and arms a T-10min
  Draftmancer reminder per event via APScheduler date jobs, re-armed on sesh edits and swept on startup.
- `fire_reminder` (`bot/tasks/pod_draft_reminder.py`) already re-fetches the sesh message at fire time and
  parses live attendees — the exact read this feature needs at T-24h / T-3h.

## The slot table

Hardcoded, single source of truth for features 1–2, in a new `bot/services/pod_schedule.py`:

| Slot | Local time | Timezone |
|---|---|---|
| Wednesday | 8:00 PM | `America/New_York` |
| Thursday | 2:00 PM | `America/New_York` |

`America/New_York` (not a fixed UTC offset) so DST shifts track ET automatically. Each slot computes its
next occurrence from a reference date; everything below renders times as Discord `<t:...:F>` timestamps so
readers see local time.

## Feature 1 — Weekly schedule post

APScheduler cron job: **Mondays 12:00 PM ET**, posting to the coordination channel
(`pod_draft_channel_id`).

- Opens with a **flavor blurb** themed to the active set, a different one each week from a curated
  per-set pool (see [Flavor pools](#flavor-pools)) so the post stays interesting for however many weeks
  the format runs.
- Below it, an embed lists the week's slots as `<t:...:F>` + `<t:...:R>` timestamp pairs. Ping-free —
  the only pings in this feature come from the underfill reminders.

### Format-boundary Mondays

Sets always release on **Tuesday**, so two Mondays around each rotation deviate from the normal post:

| Monday | Condition | Behavior |
|---|---|---|
| Release week | A seeded set releases within the next 7 days (i.e. tomorrow) | Replace the schedule post with a light opt-in message: new set drops `<t:...:R>`, regular pods paused this week, "react 👍 if you still want a pod". No `/create` DMs. |
| Championship week (last week of format) | A seeded set releases 8–13 days out | Replace the schedule post with a Set Championship promo — the season closer takes the week; no regular pods, no `/create` DMs. |

The following Monday (first full week of the new format, ~6 days after release) resumes the normal post.

**Mechanism**: `pod_schedule.py` owns an `UPCOMING_RELEASES` table of known future release dates,
independent of `ALL_SETS` so set rotation stays a one-step bump. The boundary predicates use the earliest
future date; past entries are inert. Known dates at spec time:

| Date | Set |
|---|---|
| 2026-06-23 | Marvel Super Heroes (MSH) |
| 2026-08-11 | The Hobbit (HOB) |
| 2026-09-29 | Reality Fracture (FRA) |
| 2026-11-10 | Star Trek (TRE) |

## Feature 2 — Owner `/create` DM

Sesh slash commands can't be invoked by another bot, so the bot assembles the command and the owner
copy-pastes it. Fires **immediately after the Monday post**, one DM per slot, so events exist days ahead
and accumulate RSVPs before the feature-3 checks run:

```
/create title:SOS Pod Draft #14 - June 10 datetime:June 10 8pm ET channel:#🚀-pod-draft-coordination on_create_mentions:@Any Pronouns
```

- **Set code**: active set from `bot/sets.py`.
- **`#N`**: count of `PodDraftEvent` rows for the active set + 1; the second DM of the week uses + 2.
  Best-effort — if an event gets cancelled or created out of order the owner edits the number by hand.
- **`datetime`**: full month-day + time + ET (e.g. `June 10 8pm ET`) — Sesh parses natural language
  reliably, and the full date keeps the line unambiguous regardless of when it's pasted.
- **Mentions**: a hardcoded constant for now (`@Any Pronouns` per current practice).
- **No description** — flavor lives in the Monday post only; the owner can hand-add one before pasting.

## Feature 3 — Underfill reminders (T-24h, T-3h)

Two more APScheduler date jobs per `PodDraftEvent`, mirroring the existing T-10min reminder lifecycle:
armed in `record_event`, re-armed when sesh edits move `event_time`, re-swept on startup, distinct job IDs
per window (`underfill24_{event_id}`, `underfill3_{event_id}`).

At fire time:

1. Re-fetch the sesh message and parse the live Yes count (reuse the `fire_reminder` fetch/parse path).
2. Yes count ≥ `pod_draft_target_players` (8) → stay silent.
3. Otherwise post to the coordination channel: ping `@pod drafters`, state how many more are needed,
   embed the event time as a Discord timestamp, link the sesh message (jump URL).
4. Sesh message deleted or event already started → silent skip.

A job whose fire time is already in the past at arm time (event created < 24h or < 3h out) is skipped,
never back-fired.

## Flavor pools

Copy generation is **offline and supervised** — the bot makes no AI calls. Before each set, the owner
generates candidates with GPT-5.5 (a refined per-set prompt, see guidance below), hand-picks the keepers,
and commits them; at runtime the bot only selects from the curated pool. No API key, no failure modes —
the pool is the product.

One pool per set: `MONDAY_BLURBS` in `pod_schedule.py` — short multi-line passages opening the feature-1
schedule post, sized ≥ the format's normal-week count (~5–6). Selection cycles the pool in week order,
wrapping if exhausted, so nothing repeats until everything has run once. A set with no pool falls back
to a small generic default.

### Prompt guidance (for offline curation)

Working hypotheses from early copy experiments — to be revisited against real output, not hard rules:

1. **The world speaks, never the bot.** Copy is voiced as an institution, report, or chronicler
   ("Echoverse Census Report #441", "A transmission has been received…", "It is recorded that…").
   Banned voices: bot first-person ("I saw…"), organizer ("we need players"), self-insert. This is the
   set-flavored extension of the existing no-first-person rule for bot copy.
2. **Official report → set-themed observation → joining is the correct timeline.** The call to action is
   embedded in the joke, and joining is framed as the desirable outcome — never as solving a shortage
   ("nobody signed up yet" framing is explicitly out).
3. **Give the prompt set context.** Feed it 2–3 sentences on the set's actual flavor hooks — its
   premise, factions, mechanics-as-flavor, iconic imagery — plus a few-shot example or two of the
   target shape from a previous set's pool.

## Config additions (`bot/config.py`)

| Field | Default | Purpose |
|---|---|---|
| `pod_draft_target_players` | `8` | Underfill threshold |
| `pod_drafters_role_id` | — | Role pinged by underfill reminders |
| `pod_schedule_enabled` | `True` | Master switch for the Monday post + DMs |

## Testing

Logic only, per house rules: slot-table next-occurrence math (incl. DST boundaries), the format-boundary
predicates (release week / championship week), underfill decision (count vs target, deleted message),
`/create` line assembly + `#N` numbering, flavor-pool cycling (index wrap, missing-pool default). No
tests for APScheduler firing or Discord delivery.

## Out of scope (noted in the original task)

- Bot-assisted scheduling of additional times beyond the hardcoded slot table.
- Role self-assignment management (`@Euro Pod Drafter` etc.) — roles stay manually managed; the bot only
  pings `@pod drafters` in underfill reminders.
