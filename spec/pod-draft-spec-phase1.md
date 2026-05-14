# Pod Draft Tracking — Phase 1 Spec

Status: ready for implementation. Hand this to Claude Code.
Phase 2 (native RSVP system replacing sesh.fyi) is a separate spec.

---

## Scope

Phase 1 covers:
- Detecting sesh.fyi event creation in `#pod-draft-coordination` and bootstrapping the bot
- T-5 min reminder by parsing the sesh embed
- Draftmancer session link posting, websocket connection, and session settings
- Ready check flow and automatic draft start
- Swiss bracket generation and live result tracking via websocket
- Auto-recording champion and all participants to the database
- `/pod-champions` and `/pod-stats` read commands
- Admin correction commands
- Retroactive guest → player linking at `/join` time

Phase 1 does **not** cover:
- Replacing sesh.fyi (Phase 2)
- Double pod / team draft organization (Phase 2)
- Frontend panel for pod draft stats (post-Phase 2)
- Bonus points into `PlayerSetScore`

---

## How It Works (Overview)

The organizer creates the sesh.fyi event as they do today — no extra steps.
The Dischord Bot watches `#pod-draft-coordination` for sesh's embed message,
parses it, joins the thread, and drives everything from there: reminder,
Draftmancer session setup, ready check, draft start, bracket generation, live
result posting, and champion finalization. The organizer's only new action is
running `/pod-ready` once everyone is in the Draftmancer lobby.

---

## Data Model

```
pod_draft_config                              -- single-row table (id = 1)
  id                    PK
  event_counter         INT NOT NULL          -- highest event number issued; increment per event

pod_draft_events
  id                    PK
  event_number          INT NOT NULL          -- auto-incremented from pod_draft_config
  event_date            DATE NOT NULL         -- parsed from sesh embed title
  event_time            TIMESTAMPTZ NOT NULL  -- parsed from sesh embed UTC line
  set_id                FK magic_sets.id NULL -- null for cube / throwback
  set_code              TEXT NOT NULL         -- e.g. 'SOS'; parsed from sesh embed title
  format_label          TEXT NULL             -- 'cube', 'throwback', free text; null = normal set draft
  name                  TEXT NOT NULL         -- e.g. "SOS Pod Draft #3 - May 13"
  draftmancer_session   TEXT NOT NULL         -- e.g. 'LLU-SOS-3'
  draftmancer_url       TEXT NOT NULL         -- https://draftmancer.com/?session=LLU-SOS-3
  discord_thread_id     TEXT NOT NULL         -- ID of sesh-created thread the bot joined
  sesh_message_id       TEXT NOT NULL         -- sesh embed message ID (for re-fetch at T-5)
  socket_status         TEXT NOT NULL         -- see socket_status values table below
  current_round         INT NULL              -- 1/2/3; null before bracket starts
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()

pod_draft_participants
  id                PK
  event_id          FK pod_draft_events.id ON DELETE CASCADE
  player_id         FK players.id NULL        -- null = guest; set retroactively on /join
  display_name      TEXT NOT NULL             -- as it appears in sesh embed attendee list
  draftmancer_name  TEXT NULL                 -- name player typed in Draftmancer (e.g. ArenaName#1234)
  placement         INT NULL                  -- 1 = champion; 2/3/... populated at finalization
  record            TEXT NULL                 -- '3-0', '2-1', '1-2', '0-2'
  eliminated_round  INT NULL                  -- round they went out; null = champion
  draft_log_url     TEXT NULL                 -- MagicProTools link, posted at finalization
  UNIQUE (event_id, player_id) WHERE player_id IS NOT NULL

pod_draft_matches
  id            PK
  event_id      FK pod_draft_events.id ON DELETE CASCADE
  round         INT NOT NULL                  -- 1, 2, or 3
  player_a_name TEXT NOT NULL                 -- draftmancer_name at time of match
  player_b_name TEXT NOT NULL
  winner_name   TEXT NULL                     -- null until reported in Draftmancer
  score         TEXT NULL                     -- '2-1', '2-0', etc. from bracket results array
  reported_at   TIMESTAMPTZ NULL
```

### `socket_status` values

| Value | Meaning |
|---|---|
| `pending` | Event detected; waiting for event start time |
| `connected` | Bot connected to Draftmancer websocket |
| `draft_done` | `endDraft` received; bracket generated; waiting for round 1 results |
| `bracket_active` | Round 1+ in progress |
| `complete` | Champion recorded; bot disconnected |
| `error` | Websocket connection failed after all retries |

### Data model notes

- `pod_draft_config.event_counter` is incremented atomically (SELECT FOR UPDATE)
  on each sesh embed detection so concurrent detections cannot produce duplicate
  event numbers.
- `set_id` is nullable to support cube and throwback drafts. `set_code` is always
  populated (parsed from the embed title) and drives the session name.
- `display_name` is always stored so the human-readable name is never lost even
  if a player later changes their Discord handle.
- `draftmancer_name` is populated from the `sessionUsers` websocket event — the
  free-text name the player set in Draftmancer (typically `ArenaName#1234`). This
  is what appears in bracket match data and is used to resolve match participants.
- `score` on `pod_draft_matches` is always available — the bracket `results` array
  (`[wins_a, wins_b]`) is present in every `sessionOptions` push.
- Migration: three new tables plus one config table. No changes to existing tables.

### Retroactive guest linking

Two mechanisms, both run the same underlying update:

**On `/join`** — automatic, display-name match:

```sql
UPDATE pod_draft_participants
SET player_id = :new_player_id
WHERE player_id IS NULL
AND LOWER(display_name) = LOWER(:new_discord_username)
```

Best-effort — works when the player's Discord display name matches what sesh showed
in the attendee list. Mismatches require `/pod-link-arena`.

**On `/pod-link-arena`** — manual, Arena name match:

```sql
UPDATE pod_draft_participants
SET player_id = :invoker_player_id
WHERE player_id IS NULL
AND LOWER(draftmancer_name) = LOWER(:arena_name)
```

The player supplies their exact Draftmancer name (e.g. `YourName#1234`). Catches
any case the display-name auto-link missed. Requires the player to already be
registered (i.e. have run `/join`).

---

## Sesh Embed Parsing

The bot registers an `on_message` listener in `#pod-draft-coordination`. When a
message arrives from the sesh.fyi bot (matched by `SESH_BOT_ID`), it parses the
embed:

| Field | Source in embed | Example |
|---|---|---|
| Event name | Title | `SOS Pod Draft #3 - May 13` |
| Set code | Title prefix before `Pod Draft` | `SOS` |
| Event number | Title `#N` | `3` |
| Event date | Title suffix | `May 13` + current year |
| Event time (UTC) | `Timezone Conversions` field, UTC line | `Thursday, May 14 12:00am UTC` |
| Attendees (Yes) | `✅ Attendees (N)` section, newline-delimited | `Arcyl`, `WaveofShadow`, … |

**Parsing strategy:**

- Parse UTC time from the `Timezone Conversions` line — more reliable than
  converting the local time line which may be ambiguous across timezones.
- Extract attendees by reading lines between `✅ Attendees (N)` and the next
  section header (`🤔 Maybe` or `❌ No`). Trim whitespace from each line.
- If `event_number` does not equal `pod_draft_config.event_counter + 1`, log a
  warning and adopt the parsed number, updating the counter to match.

**On detection:**

1. Parse all fields above.
2. Increment `pod_draft_config.event_counter` (atomic).
3. Create `pod_draft_events` row (`socket_status = 'pending'`).
4. Poll for the sesh-created thread on that message: check every 5 seconds for
   up to 2 minutes (sesh creates the thread shortly after posting the embed).
5. Join the thread; save `discord_thread_id` and `sesh_message_id` to DB.
6. Schedule the T-5 min APScheduler task for `event_time - 5 minutes`.
7. Post a quiet confirmation in the thread (no ping):

   > 🤖 Pod Draft #N registered. I'll post the Draftmancer link 5 minutes before
   > the event starts.

---

## Event Lifecycle

```
Organizer runs sesh /create
  └─ Sesh posts embed in #pod-draft-coordination + creates thread

Bot detects sesh embed (on_message, sender = SESH_BOT_ID)
  ├─ Parses embed → pod_draft_events row (socket_status = 'pending')
  ├─ Polls for thread → joins thread
  └─ Schedules APScheduler task at event_time - 5 min

──────────────── T-5 min ────────────────

APScheduler fires
  ├─ Re-fetches sesh message → re-parses ✅ Attendees (may have changed)
  ├─ Resolves Discord user IDs from display names (best-effort guild member lookup)
  ├─ Posts in thread:
  │     🎴 Pod Draft #N starts in 5 minutes!
  │     @Player1 @Player2 … (Yes attendees only)
  │     Join: https://draftmancer.com/?session=LLU-SOS-3
  │     Set your Draftmancer name to your Arena name (e.g. YourName#1234)
  └─ Instantiates PodDraftManager → connects to Draftmancer websocket
       emits join sequence + session settings
       socket_status = 'connected'

──────────────── Lobby phase ────────────────

on sessionUsers  → update internal user list
                   upsert pod_draft_participants with draftmancer_name

Anyone runs /pod-ready
  → bot checks all expected players present in sessionUsers
  → emits readyCheck to Draftmancer (native ready check UI appears for all players)
  → posts ready check message in thread: "0/N ready"
  → 90s timeout task starts

on setReady(userID, readyState)
  → update ready_users set
  → edit thread message: "3/6 ready — waiting on: PlayerD, PlayerE"
  → if len(ready_users) >= expected_count:
      wait 5s → emit startDraft → post "🎴 Draft started!" in thread

──────────────── Draft phase ────────────────

on endDraft
  → post "Draft complete! Export your deck to Arena." in thread
  → socket_status = 'draft_done'
  → emit generateBracket('Swiss')
  → Draftmancer responds with sessionOptions: round 1 seeded

on draftLog      → store per-user log data for MagicProTools links at finalization

──────────────── Bracket phase ────────────────

on sessionOptions (bracket present, round 1 newly seeded)
  → socket_status = 'bracket_active', current_round = 1
  → post Round 1 pairings in thread

on sessionOptions (match result updated, match now complete)
  → debounce 3s → re-read bracket → commit if stable
  → write pod_draft_matches row
  → post: 🎮 Round N · WinnerName wins 2-1 vs LoserName

on sessionOptions (round N+1 newly seeded — same push as last round N result)
  → post Round N+1 pairings with current records
  → current_round = N+1

on sessionOptions (any round 3 match complete)
  → sum wins per player across all matches
  → if any player has 3 wins → champion finalization

──────────────── Champion finalization ────────────────

  1. Compute final records for all players from bracket match data
  2. Write pod_draft_participants: placement, record, eliminated_round for all
     Champion: placement = 1, record = '3-0', eliminated_round = null
  3. socket_status = 'complete'
  4. Assemble MagicProTools URLs from stored draftLog socket data
  5. Post champion announcement + standings + draft log links in thread
  6. Disconnect websocket; remove PodDraftManager from ACTIVE_POD_MANAGERS
```

---

## Draftmancer Websocket Integration

### Connection

`python-socketio` async client. One `PodDraftManager` instance per active event,
stored in `ACTIVE_POD_MANAGERS: dict[event_id, PodDraftManager]`. Reconnects with
exponential backoff + jitter on disconnect (same pattern as `Amelas22/DraftBot`).

**Join sequence** (emitted immediately after `connect`):

```python
await sio.emit('joinSession', {
    'sessionID': 'LLU-SOS-3',
    'userName': 'DisChordBot',
    'useCollection': False,
})
await sio.emit('setOwnerIsPlayer', False)   # session owner but not a drafter
```

### Session Settings

Emitted immediately after joining, before any players arrive:

```python
await sio.emit('setOwnerIsPlayer', False)           # no draft seat
await sio.emit('setMaxPlayers', 8)                  # from env POD_DRAFT_MAX_PLAYERS
await sio.emit('setPickTimer', 60)                  # from env POD_DRAFT_PICK_TIMER
await sio.emit('setColorBalance', False)            # no color balancing
await sio.emit('setPersonalLogs', True)             # per-player draft logs enabled
await sio.emit('setDraftLogRecipients', "delayed")  # logs released after event
```

`POD_DRAFT_MAX_PLAYERS` and `POD_DRAFT_PICK_TIMER` are env vars so cube events
can use different values without code changes.

### Events Listened To

| Draftmancer event | Payload | Bot action |
|---|---|---|
| `connect` | — | Emit join sequence + session settings; `socket_status = 'connected'` |
| `sessionUsers` | `[{userID, userName}, …]` | Update user list; upsert `draftmancer_name` per participant |
| `setReady` | `(userID, readyState)` | Update `ready_users`; edit thread message; start draft if all ready |
| `endDraft` | — | Post "Draft complete"; `socket_status = 'draft_done'`; emit `generateBracket('Swiss')` |
| `draftLog` | log object | Store per-user log for MagicProTools links at finalization |
| `sessionOptions` | full session state | Bracket tracking — round seeding, result diffs, champion detection |
| `disconnect` | — | Log; reconnect with exponential backoff + jitter |

### Bracket Protocol (confirmed from live session capture)

**Generating the bracket:**

```python
await sio.emit('generateBracket', 'Swiss')
# Draftmancer immediately pushes sessionOptions with round 1 seeded
```

**`sessionOptions` bracket payload shape:**

```json
{
  "bracket": {
    "type": "Swiss",
    "players": [
      {"userID": "uuid-0", "userName": "PlayerA#1234"},
      {"userID": "uuid-1", "userName": "PlayerB#5678"},
      {"userID": "uuid-2", "userName": "PlayerC#9012"},
      {"userID": "uuid-3", "userName": "PlayerD#3456"},
      {"userID": "uuid-4", "userName": "PlayerE#7890"},
      {"userID": "uuid-5", "userName": "PlayerF#2345"}
    ],
    "matches": [
      {"id": 0, "players": [0, 1], "results": [0, 0]},
      {"id": 1, "players": [2, 3], "results": [0, 0]},
      {"id": 2, "players": [4, 5], "results": [0, 0]},
      {"id": 3, "players": [-1, -1], "results": [0, 0]},
      {"id": 4, "players": [-1, -1], "results": [0, 0]},
      {"id": 5, "players": [-1, -1], "results": [0, 0]},
      {"id": 6, "players": [-1, -1], "results": [0, 0]},
      {"id": 7, "players": [-1, -1], "results": [0, 0]},
      {"id": 8, "players": [-1, -1], "results": [0, 0]}
    ],
    "bracket": [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
  }
}
```

After round 1 completes, the same push that delivers the final round 1 result
also seeds round 2 (players `[-1,-1]` → real indices):

```json
{"id": 3, "players": [0, 2], "results": [0, 0]},
{"id": 4, "players": [4, 1], "results": [0, 0]},
{"id": 5, "players": [5, 3], "results": [0, 0]},
```

**Bracket data key:**

- `players` — indexed array of all participants (0–N)
- `matches[i].players` — `[idx_a, idx_b]` into the `players` array;
  `[-1, -1]` = not yet seeded
- `matches[i].results` — `[wins_a, wins_b]`
- `bracket` — `[[round1_match_ids], [round2_match_ids], [round3_match_ids]]`
  - 6-player pod: 3 matches per round, 9 total
  - 8-player pod: 4 matches per round, 12 total
  - The `bracket` array is always the source of truth regardless of player count

**Result state table:**

| `players` | `results` | State |
|---|---|---|
| `[-1, -1]` | any | Not seeded |
| real indices | `[0, 0]` | Seeded, not started |
| real indices | `[1, 0]` or `[0, 1]` | In progress |
| real indices | `[2, x]` or `[x, 2]` | Complete (first to 2 wins) |

**Key behaviours:**
- Players report results in Draftmancer themselves. The bot does NOT emit
  `updateBracket`. Draftmancer pushes a full `sessionOptions` to all connected
  clients on every result update.
- Round N+1 is seeded by Draftmancer in the same `sessionOptions` push that
  delivers the final result of round N. There is no separate round-advance event.
- **Champion detection — Swiss, no designated Finals match.** The champion is the
  first player to accumulate 3 wins. After each round 3 match result, sum wins
  per player index across all completed matches. First player to 3 wins wins.

### Bracket Result Processing

On each `sessionOptions` event where `bracket` is present:

```
1. If this is the first sessionOptions with bracket data (socket_status = 'draft_done'):
   → Store full bracket state in memory as last_bracket_state
   → Detect which rounds are already seeded (players != [-1,-1])
   → Post pairings for round 1
   → socket_status = 'bracket_active', current_round = 1
   → Return (no result diffs to process on initial push)

2. Diff incoming matches against last_bracket_state.

3. Detect newly seeded rounds:
   For each round group in bracket[]:
     If ALL matches in this group were previously [-1,-1] AND now have real players:
       → Post pairings for this round with each player's current record
       → current_round = this round index + 1

4. For each match where results changed AND match is now complete (max(results) >= 2):
   a. Schedule debounce: asyncio.create_task with 3s sleep
   b. After 3s, re-read current last_bracket_state (may have been updated)
   c. If results still match (not corrected by player): commit
      - player_a = players[match.players[0]].userName
      - player_b = players[match.players[1]].userName
      - winner   = player_a if results[0] > results[1] else player_b
      - score    = f"{max(results)}-{min(results)}"
      - Write pod_draft_matches row
      - Post: 🎮 Round N · {winner} wins {score} vs {loser}

5. After committing any round 3 result:
   Compute wins per player: wins[player_idx] = sum of results[pos] across all
   completed matches where match.players[pos] == player_idx.
   If any player has wins[i] == 3: trigger champion finalization for
   players[i].userName.

6. Update last_bracket_state = incoming bracket state.
```

**Dropped player detection:** after each result commit, for each player whose
total wins + remaining unseeded matches < 2 (cannot mathematically reach 2 wins),
set `eliminated_round = current_round` on their `pod_draft_participants` row.
Dropped players appear in final standings but do not block finalization.

### Ready Check State Machine

```
/pod-ready invoked
  → look up active event (socket_status = 'connected', event_date = today)
  → if none: ephemeral "No active pod draft session right now."
  → if ready check already active: ephemeral "Ready check already in progress."
  → check len(non_bot sessionUsers) >= expected_player_count
    No  → ephemeral "⚠️ Not everyone is in Draftmancer yet.
                     Missing: PlayerA, PlayerB"
    Yes → emit readyCheck
          ready_users = set()
          post in thread: "🔔 Ready check started! Click Ready in Draftmancer.
                           0/N ready — waiting on: PlayerA, PlayerB, …"
          start 90s timeout task

on setReady(userID, 1 or "Ready"):
  ready_users.add(userID)
  edit thread message: "🔔 3/6 ready — waiting on: PlayerD, PlayerE"
  if len(ready_users) >= expected_player_count:
    cancel timeout task
    post: "🎉 All drafters ready! Draft starting in 5 seconds..."
    await asyncio.sleep(5)
    await sio.emit('startDraft', callback=ack)
    on ack success → post: "🎴 Draft started! Happy drafting everyone."
    on ack error   → post: "⚠️ Could not start draft: {error}. Start manually."

on setReady(userID, 0 or "NotReady"):
  ready_users.discard(userID)
  edit thread message accordingly

on sessionUsers (player count changes while ready_check_active):
  cancel timeout task
  ready_users = set()
  post: "⚠️ Ready check cancelled — player list changed. Run /pod-ready again."

on timeout (90s expires):
  ready_users = set()
  post: "⚠️ Ready check timed out. Run /pod-ready when everyone is in Draftmancer."
```

---

## Thread Message Formats

### T-5 min reminder
```
🎴 Pod Draft #3 starts in 5 minutes!
@Arcyl @WaveofShadow @Oophies @elton @Luke @Chonce

Join the Draftmancer session: https://draftmancer.com/?session=LLU-SOS-3

Set your Draftmancer name to your Arena name (e.g. YourName#1234) so
pairings and friend requests work smoothly.
```

### Round 1 pairings (posted on bracket generation)
```
🎴 Draft complete! Export your deck to Arena.

━━━ Round 1 Pairings ━━━
⚔️  PlayerA  vs  PlayerB
⚔️  PlayerC  vs  PlayerD
⚔️  PlayerE  vs  PlayerF
```

### Round 2 / 3 pairings (posted when round becomes seeded)
```
✅ Round 1 complete!

━━━ Round 2 Pairings ━━━
⚔️  PlayerA (1-0)  vs  PlayerC (1-0)
⚔️  PlayerE (1-0)  vs  PlayerB (0-1)
⚔️  PlayerF (0-1)  vs  PlayerD (0-1)
```

### Round 3 pairings
```
✅ Round 2 complete!

━━━ Round 3 Pairings ━━━
⚔️  PlayerA (2-0)  vs  PlayerC (2-0)   ← trophy match
⚔️  PlayerE (1-1)  vs  PlayerB (1-1)
⚔️  PlayerF (0-2)  vs  PlayerD (0-2)
```

### Match result line
```
🎮 Round 2 · Oophies wins 2-1 vs Noya
```

### Champion finalization post
```
🏆 Pod Draft #3 Champion: @PlayerName (3-0)!

Final standings:
🥇 PlayerName    3-0
🥈 PlayerB       2-1
🥉 PlayerC       1-2
   PlayerD       0-2
   PlayerE       1-2
   PlayerF       0-2

📋 Draft logs:
• PlayerName — https://magicprotools.com/...
• PlayerB    — https://magicprotools.com/...
• PlayerC    — https://magicprotools.com/...
• PlayerD    — https://magicprotools.com/...
• PlayerE    — https://magicprotools.com/...
• PlayerF    — https://magicprotools.com/...

Post your final decklist screenshot in this thread! 🎴
```

Placement emoji: 🥇 = 3-0, 🥈 = 2-1, 🥉 = 1-2, no emoji for 0-2.
Multiple players with the same record: sort alphabetically within the tier.
@mention the champion only; other players listed by draftmancer_name.

---

## Commands

### `/pod-ready` (anyone)

Triggers a Draftmancer ready check for today's active pod draft session.
See Ready Check State Machine above for full logic.

### `/pod-champions [set:]` (anyone)

Lists champions grouped by set code. Without `set:`, defaults to current set.
Cube and throwback events appear in a separate section labelled by `format_label`.

```
🏆 SOS Pod Draft Champions
#1 — May 6   · PlayerA
#2 — May 13  · PlayerB
#3 — May 20  · PlayerC

🎲 Cube / Special Events
#1 — Apr 15  · PlayerD  (Vintage Cube)
```

### `/pod-stats [player:]` (anyone)

Per-player career view. Without `player:`, shows invoker's stats.

```
🎴 Pod Draft Stats — PlayerName
Trophies:     2 lifetime · 1 in SOS
Events played: 5
Record:        12-3
```

Omit Record line if no `pod_draft_matches` data exists for the player.

### `/stats` augmentation

When a player has any pod-draft history, append to the existing `/stats` output:
`Pod trophies: 2 lifetime · 1 in SOS`. Omit entirely when zero.

### `/pod-link-arena <arena_name>` (anyone, must be registered)

Links the invoker's past pod draft guest records to their registered player account
by matching on `draftmancer_name`.

**Flow:**

1. Verify invoker has a `players` row (has run `/join`). If not: ephemeral error
   "You need to run `/join` first."
2. Run the Arena name match update. Count affected rows.
3. If 0 rows matched: ephemeral "No unlinked pod draft records found for
   `{arena_name}`. Check that it matches exactly what you typed in Draftmancer."
4. If N rows matched: ephemeral "✅ Linked {N} pod draft event(s) to your account."

The `arena_name` argument is case-insensitive but must otherwise match exactly
(e.g. `YourName#1234`).

### `/pod-result-edit <event_id> <player_name> <field> <value>` (admin role)

Corrects a participant or match record post-hoc.
Editable fields: `placement`, `record`, `winner_name`, `score`, `eliminated_round`.

### `/pod-result-delete <event_id>` (admin role)

Removes a spurious event row entirely (cascades to participants and matches).
Bot sends an ephemeral confirmation prompt before executing.

---

## New Files

```
bot/
├── listeners/
│   └── sesh_listener.py
│       # on_message in #pod-draft-coordination
│       # filter by SESH_BOT_ID, parse embed, create DB row,
│       # poll for thread (5s / 2min), join thread, schedule reminder
│
├── tasks/
│   └── pod_draft_reminder.py
│       # APScheduler task fired at event_time - 5min
│       # re-fetch sesh embed, parse attendees, resolve Discord IDs,
│       # post ping message, instantiate PodDraftManager, connect
│
├── services/
│   ├── pod_drafts.py
│   │   # record_event(parsed_embed_data) -> PodDraftEvent
│   │   # upsert_participant(event_id, display_name, draftmancer_name=None)
│   │   # record_match(event_id, round, player_a, player_b, winner, score)
│   │   # finalize_champion(event_id, bracket_players, all_matches, draft_log_data)
│   │   # link_guest_on_join(discord_username, new_player_id)
   │   # link_guest_on_arena_name(player_id, arena_name) -> int  (rows updated)
│   │   # list_champions(set_code=None) -> list[dict]
│   │   # player_pod_stats(discord_id) -> dict
│   │
│   └── pod_draft_manager.py
│       # PodDraftManager — owns socket lifecycle for one pod draft event
│       #
│       # ACTIVE_POD_MANAGERS: dict[event_id, PodDraftManager]  (module-level)
│       #
│       # __init__(event_id, session_id, thread_id, expected_players)
│       # connect()                     — join session, emit settings
│       # disconnect_safely()           — clean disconnect, remove from registry
│       #
│       # _on_connect()
│       # _on_disconnect()
│       # _on_session_users(users)      — upsert participants, track user count
│       # _on_set_ready(userID, state)  — ready check tracking
│       # _on_end_draft(data)           — post msg, emit generateBracket
│       # _on_draft_log(log)            — store for MagicProTools links
│       # _on_session_options(data)     — bracket tracking entry point
│       #
│       # initiate_ready_check()
│       # _handle_ready_update(userID, state)
│       # _complete_ready_check()
│       # _start_draft()
│       #
│       # _process_bracket(bracket_state)   — diff, seeding detection, debounce
│       # _commit_match_result(match, bracket_players)
│       # _detect_champion(bracket_players, all_matches) -> str | None
│       # _finalize_champion(winner_name)
│
├── commands/
│   └── pod_draft.py
│       # /pod-ready
│       # /pod-champions
│       # /pod-stats
│       # /pod-link-arena
│       # /pod-result-edit
│       # /pod-result-delete
│
└── models.py
    # add: PodDraftConfig, PodDraftEvent, PodDraftParticipant, PodDraftMatch
```

---

## New Environment Variables

```
POD_DRAFT_CHANNEL_ID=           # Discord channel ID for #pod-draft-coordination
POD_DRAFT_SESSION_PREFIX=LLU    # fixed prefix for session names (e.g. LLU-SOS-3)
POD_DRAFT_MAX_PLAYERS=8         # passed to setMaxPlayers on connect
POD_DRAFT_PICK_TIMER=60         # passed to setPickTimer on connect (seconds)
SESH_BOT_ID=                    # Discord user ID of the sesh.fyi bot
DRAFTMANCER_WS_URL=wss://draftmancer.com
```

---

## Implementation Order

Each step is independently testable before the next begins.

1. **Migration** — create `pod_draft_config`, `pod_draft_events`,
   `pod_draft_participants`, `pod_draft_matches`. Seed `pod_draft_config` with
   `event_counter = 3` (current highest event number).

2. **Models** — `PodDraftConfig`, `PodDraftEvent`, `PodDraftParticipant`,
   `PodDraftMatch` SQLAlchemy models in `models.py`.

3. **`pod_drafts.py`** — all DB business logic: `record_event`, `upsert_participant`,
   `record_match`, `finalize_champion`, `link_guest_on_join`, `list_champions`,
   `player_pod_stats`. No socket dependency; fully unit-testable.

4. **`sesh_listener.py`** — `on_message` handler: filter by `SESH_BOT_ID`, parse
   embed fields, create DB row, poll for thread (5s / 2min), join thread, save IDs,
   schedule APScheduler task.

5. **`pod_draft_manager.py`** skeleton — connect, emit join sequence + settings,
   `_on_session_users`, reconnect with backoff. Test by connecting to a live
   Draftmancer session and verifying `sessionUsers` events arrive.

6. **`pod_draft_reminder.py`** — APScheduler task: re-fetch sesh message, parse
   attendees, resolve Discord user IDs via guild member lookup, post ping, call
   `PodDraftManager.connect()`.

7. **Ready check + draft start** — `initiate_ready_check`, `_handle_ready_update`,
   `_complete_ready_check`, `_start_draft` on the manager. Add `/pod-ready` command.

8. **Bracket generation** — `_on_end_draft`: post "Draft complete", emit
   `generateBracket('Swiss')`, store initial bracket from responding `sessionOptions`.

9. **Bracket result processing** — `_on_session_options` / `_process_bracket`:
   diff matches, detect newly seeded rounds, post pairings, debounce commits, post
   result lines, detect 3-0 champion.

10. **Champion finalization** — `_finalize_champion`: compute records, write all DB
    rows, assemble MagicProTools links from stored `draftLog` data, post standings
    announcement, disconnect.

11. **Read commands** — `/pod-champions`, `/pod-stats`, `/stats` augmentation.

12. **Admin commands** — `/pod-result-edit`, `/pod-result-delete`.

13. **Guest linking** — call `link_guest_on_join` in existing `/join` command flow
    after the `players` row is committed. Add `/pod-link-arena` command calling
    `link_guest_on_arena_name(invoker_player_id, arena_name)`.

14. **Tests:**
    - Sesh embed parsing: normal set, cube event, attendee count changed between
      detection and T-5, UTC time parsing across midnight boundary
    - Thread poll: found immediately, found after delay, timeout path
    - Bracket diff: initial seeding, incremental result update, round-advance
      detection in same push, 8-player pod shape
    - Debounce: result corrected within 3s window (should not commit wrong result)
    - Champion detection: clean 3-0, 8-player bracket
    - Dropped player: `eliminated_round` set correctly
    - Finalization: DB writes correct, message format, MagicProTools URL assembly
    - Guest linking: display-name case-insensitive match on `/join`, no match
      (no-op), multiple past events all linked; `/pod-link-arena` exact match,
      case-insensitive match, no match, unregistered invoker error
    - Ready check: invalidation on player join/leave, timeout path, all-ready path,
      `startDraft` ack error handling

---

## Out of Scope for Phase 1

- Replacing sesh.fyi (Phase 2)
- Auto-scheduled weekly event creation (Phase 2)
- Second pod organization when 9+ Yes RSVPs (Phase 2)
- RSVP editing / un-RSVP via bot (Phase 2)
- Thread auto-add/remove on RSVP change (Phase 2)
- Late RSVP handling after event start (Phase 2)
- Frontend / web panel for pod draft stats (post-Phase 2)
