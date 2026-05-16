# Pod Draft Tracking — Phase 2 Spec

Status: design complete for decided items; TBD items deferred to implementation time.
Do not implement Phase 2 until Phase 1 is shipped and stable.

---

## Scope

Phase 2 replaces sesh.fyi entirely. The Dischord Bot owns the full event lifecycle:
creation, RSVP collection, thread management, reminders, and edit notifications.
Everything Phase 1 does from the T-5 min reminder onward is unchanged.

Phase 2 adds:
- `/pod-draft` command (bot creates event + RSVP embed + thread)
- Native RSVP buttons (Yes / Maybe / No) with DB-backed state
- Auto thread add/remove on RSVP change
- RSVP closes at event start time
- `@pod-drafters` ping on event creation
- Discord Scheduled Event creation alongside the embed
- `/pod-edit` command for post-creation changes
- Auto-scheduled weekly event creation
- Second pod auto-organization when attendance is high

Phase 2 does **not** change anything in the Draftmancer socket pipeline, bracket
tracking, or champion finalization. Those are Phase 1 and remain untouched.

---

## What Changes vs Phase 1

| Concern | Phase 1 | Phase 2 |
|---|---|---|
| Event creation | Organizer runs sesh `/create` manually | Organizer runs `/pod-draft` on Dischord Bot |
| Bot entry point | `on_message` detects sesh embed | `/pod-draft` command handler |
| RSVP data source | Parse sesh embed text at T-5 min | Query `pod_draft_rsvps` table |
| Thread creation | Sesh creates it; bot joins | Bot creates it on the RSVP message |
| Thread membership | Sesh manages | Bot manages on every RSVP change |
| `sesh_listener.py` | Active | Removed |
| `sesh_message_id` | Used for embed re-fetch | Replaced by `rsvp_message_id` |

Everything else in Phase 1 carries forward unchanged.

---

## Data Model Changes

### New table

```
pod_draft_rsvps
  id              PK
  event_id        FK pod_draft_events.id ON DELETE CASCADE
  discord_user_id TEXT NOT NULL
  display_name    TEXT NOT NULL              -- snapshot at time of RSVP
  status          TEXT NOT NULL             -- 'yes' | 'maybe' | 'no'
  responded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  UNIQUE (event_id, discord_user_id)
```

### Changes to `pod_draft_events`

Remove: `sesh_message_id`
Add:

```
rsvp_message_id       TEXT NULL    -- ID of the bot's RSVP embed message
scheduled_event_id    TEXT NULL    -- Discord Scheduled Event ID
auto_scheduled        BOOLEAN NOT NULL DEFAULT false  -- true if created by weekly task
```

---

## `/pod-draft [set:] [date:] [time:] [format:]` (organizer role)

Creates a new pod draft event. The organizer no longer needs to touch sesh.fyi.

**Options:**

| Option | Description | Default |
|---|---|---|
| `set:` | Set code (e.g. `SOS`) | Current set from config |
| `date:` | Event date | Next occurrence of configured weekly day |
| `time:` | Event time in server local time (e.g. `21:00`) | Configured weekly time |
| `format:` | Free text for cube / throwback label | — |

**Flow:**

1. Validate organizer role.
2. Increment `pod_draft_config.event_counter` atomically.
3. Create `pod_draft_events` row (`socket_status = 'pending'`).
4. Create a Discord Scheduled Event for the date/time (requires `MANAGE_EVENTS`).
5. Post RSVP embed in `#pod-draft-coordination`, pinging `@pod-drafters`:

   ```
   @pod-drafters

   📅 SOS Pod Draft #N — <t:TIMESTAMP:F>

   Click a button below to RSVP.

   ✅ Going (0)
   🤔 Maybe (0)
   ❌ Can't make it (0)
   ```

6. Create a thread on that message named `"SOS Pod Draft #N — May 13"`.
7. Save `rsvp_message_id`, `discord_thread_id`, `scheduled_event_id` to DB.
8. Post confirmation in the thread (no ping):

   > 🤖 Pod Draft #N registered for <t:TIMESTAMP:F>. RSVP above — I'll post the
   > Draftmancer link 5 minutes before we start.

---

## RSVP System

### Buttons

The RSVP embed has three persistent buttons: ✅ Going, 🤔 Maybe, ❌ Can't make it.
Implemented as Discord UI components (not reactions) so user IDs are directly
available on interaction — no embed parsing needed.

Buttons are disabled at `event_time` (RSVP closed). Any interaction after that
gets an ephemeral "RSVPs are closed for this event."

### On RSVP button press

1. Upsert `pod_draft_rsvps` row for `(event_id, discord_user_id)` with new status.
2. Update the embed to reflect new counts (edit the RSVP message).
3. Manage thread membership:

   | Previous status | New status | Thread action |
   |---|---|---|
   | none / no | yes | Add to thread |
   | none / no | maybe | Add to thread |
   | yes / maybe | no | Remove from thread |
   | yes | maybe | No change (already in thread) |
   | maybe | yes | No change (already in thread) |
   | yes / maybe | same | No change |

4. No DM or channel notification — the embed update is the only feedback.

### RSVP embed live format

```
@pod-drafters

📅 SOS Pod Draft #3 — Wednesday, May 13 at 9:00 PM EDT

✅ Going (8)
Arcyl · WaveofShadow · Oophies · elton
Luke · Chonce · Doctormagi · Bacchus

🤔 Maybe (4)
Noya · NiamhIsTired · Sheesh · gogey

❌ Can't make it (4)
g-rey2996 · Wasabi · Hare Krishna · Suriname
```

Time shown using Discord native timestamp (`<t:UNIX:F>`) so each user sees it
in their local timezone automatically.

---

## Thread Auto-Management

When a player RSVPs Yes or Maybe: `thread.add_member(user_id)`.
When a player changes to No: `thread.remove_member(user_id)`.
The organizer and bot are always in the thread regardless of RSVP status.

---

## `/pod-edit` (organizer role)

Edits an upcoming pod draft event. All fields optional; supply only what changes.

**Options:** `set:`, `date:`, `time:`, `format:`

**On time change:**
1. Update `pod_draft_events.event_time`.
2. Reschedule the APScheduler T-5 min task.
3. Update the Discord Scheduled Event time.
4. Edit the RSVP embed timestamp.
5. Post notification in the event thread:

   > 📢 Time update: Pod Draft #N has been rescheduled to <t:NEW_TIMESTAMP:F>.

---

## Auto-Scheduled Weekly Creation

An APScheduler cron task fires at the configured weekly day/time (e.g. every
Tuesday at noon) and calls the same logic as `/pod-draft` with default parameters.
The organizer can still run `/pod-draft` manually to override or create an extra
event.

Config (env vars or single-row config table — TBD at implementation):
- Day of week
- Default time
- Default set (falls back to current set from existing config)

If an event already exists for that week, the task skips silently and logs.

---

## Second Pod Auto-Organization

**TBD at implementation time.** The following is directional only.

Trigger: when Yes RSVP count reaches a threshold (likely 9), the bot posts a
notice in the thread that a second pod may be organized. At event start (or
T-5 min), if Yes count exceeds the threshold, the bot creates a second
Draftmancer session and splits players into two pods.

Open questions deferred:
- Exact threshold (8? 9? configurable?)
- Split format: two pods of 6 for 12 players, two pods of 4+4 for 8–9, etc.
- Whether team draft (3v3) is ever auto-organized or always manual
- How players are assigned to pods (sign-up order, random, manual organizer input)
- Whether two separate threads are created or one shared thread

---

## New / Changed Files vs Phase 1

```
bot/
├── listeners/
│   └── sesh_listener.py        ← REMOVED in Phase 2
│
├── tasks/
│   ├── pod_draft_reminder.py   -- unchanged; reads pod_draft_rsvps instead of sesh embed
│   └── pod_draft_scheduler.py  -- NEW: weekly cron task to auto-create events
│
├── services/
│   ├── pod_drafts.py           -- add: create_event, upsert_rsvp, get_yes_attendees
│   └── pod_draft_manager.py    -- unchanged
│
├── commands/
│   └── pod_draft.py            -- add: /pod-draft, /pod-edit
│                                  keep: /pod-ready, /pod-champions, /pod-stats,
│                                        /pod-link-arena, /pod-result-edit,
│                                        /pod-result-delete
│
└── models.py
    -- add: PodDraftRsvp
    -- modify: PodDraftEvent (add rsvp_message_id, scheduled_event_id, auto_scheduled;
                               remove sesh_message_id)
```

---

## New Environment Variables

```
POD_DRAFT_WEEKLY_DAY=2          # Day of week for auto-schedule (0=Mon, 2=Wed, etc.)
POD_DRAFT_WEEKLY_TIME=21:00     # Default event time in server local time
POD_DRAFT_TIMEZONE=America/New_York  # Server timezone for scheduled event display
POD_DRAFTERS_ROLE_ID=           # Role ID for @pod-drafters ping on event creation
```

Existing Phase 1 vars (`POD_DRAFT_CHANNEL_ID`, `POD_DRAFT_SESSION_PREFIX`, etc.)
are unchanged.

---

## Migration from Phase 1

1. Add `pod_draft_rsvps` table.
2. Add `rsvp_message_id`, `scheduled_event_id`, `auto_scheduled` columns to
   `pod_draft_events`.
3. Drop `sesh_message_id` column (or keep nullable for historical rows).
4. Remove `sesh_listener.py` and its APScheduler registration.
5. Existing `pod_draft_events` rows from Phase 1 are unaffected — they have
   `sesh_message_id` set and `rsvp_message_id` null, which is fine since those
   events are already complete.

---

## Out of Scope for Phase 2

- Web dashboard for event management
- RSVP waitlist (beyond the second-pod threshold notice)
- DM reminders to individual attendees
- Integration with any external calendar service
- Match scheduling / opponent coordination within the thread
