# Pod Draft Tracking — Spec / Plan

Status: design draft. Not built. Decisions captured below come from the brainstorm
on 2026-05-03; open items are flagged inline.

---

## Goal

Record the outcomes of the server's organized weekly pod draft events so champions
are remembered and (eventually) per-player career stats are queryable. Pod drafts
typically run on Draftmancer (draft) + MTGA (swiss matches), 6–8 players, single
champion at the end (3-0).

This is a **separate axis from the 17lands-driven leaderboard**. It does not feed
`PlayerSetScore` or the `/leaderboard` ranking.

---

## Confirmed decisions

1. **Reporter trust model: self-report.** Anyone can submit a result. No role gate
   for now. Open question: moderation / dispute flow (see below).
2. **Participant identity: registered players or guests.** Participants in a pod
   are not required to have run `/join`. Guests are stored by display name only,
   not linked to a `players` row.
3. **Recording depth: Tier 2, best-effort.** At minimum the **winner** is required.
   Other participants and their records are optional and can be filled in later.
4. **Scoring: separate trophy count.** No bonus into `PlayerSetScore`. A
   championship is one pod-draft trophy. Surface as a "Pod trophies" stat.
5. **Set scope: includes cube and throwback drafts.** Events are not required to
   anchor to the active set — `set_id` is nullable.

---

## Data model (proposed)

```
pod_draft_events
  id              PK
  event_date      DATE NOT NULL
  set_id          FK magic_sets.id NULL    -- null for cube / throwback
  format_label    TEXT NULL                -- 'cube', 'throwback', free text; null = current set draft
  name            TEXT NULL                -- e.g. "Weekly Pod #42"
  draftmancer_url TEXT NULL
  notes           TEXT NULL
  reported_by_discord_id TEXT NOT NULL
  reported_at     TIMESTAMPTZ NOT NULL DEFAULT now()
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()

pod_draft_participants
  id           PK
  event_id     FK pod_draft_events.id ON DELETE CASCADE
  player_id    FK players.id NULL          -- null = guest
  display_name TEXT NOT NULL               -- always rendered name; guest name when player_id null
  placement    INT NULL                    -- 1 = champion, 2/3/... optional
  record       TEXT NULL                   -- '3-0', '2-1', etc.
  UNIQUE (event_id, player_id) WHERE player_id IS NOT NULL
```

Notes:

- `placement = 1` is the canonical "champion" marker. Tier 2 best-effort means
  every event has at least one row with `placement = 1`; everything else is
  optional. Higher placements (2nd, 3rd) can be filled in if known.
- `display_name` is always populated so we never lose the human-readable name,
  even if a player later changes their Discord handle or gets removed.
- `format_label` plus nullable `set_id` keeps the schema simple. `set_id` IS NULL
  ⟹ event is cube/throwback/other; the label says which.
- A guest who later joins via `/join` can be linked retroactively by an admin
  command (not in v1 scope) — `player_id` becomes settable post-hoc.

Migration risk is contained: this is two new tables, no changes to existing ones.

---

## Bot UX

### `/pod-result` (anyone)

Walkthrough flow (DM-friendly), modal-based:

1. Date (defaults to today).
2. Set or format: dropdown of active sets + "Cube" + "Throwback" + "Other".
3. Champion: autocompleted from registered players, free-text fallback for guest.
4. Optional fields: other participants (multi-add), records, Draftmancer URL,
   event name, notes.

Posts a result embed in a configured pod-results channel and a confirmation in
the reporter's DM.

### `/champions [set]`

Public read. Lists champions for the active set by default; `set:` arg filters.
Cube / throwback events get their own section.

### `/pod-stats [player]`

Per-player career view: pod trophies (lifetime + current set), events played,
record summary if data is present.

### `/stats` augmentation

When a player has any pod-draft history, append a one-line block:
`Pod trophies: 3 lifetime · 1 in SOS`. Skip when zero.

---

## Surfacing on the future site

- Top-level "Pod Draft Champions" panel — chronological list, latest first.
- Each player profile page shows pod trophies alongside their 17lands-driven
  score.
- Cube / throwback events surface in a separate sub-panel (or filter chip) so
  set-anchored champions stay sortable by set.

---

## Anti-abuse / moderation (open)

Self-report at v1 means bad actors can submit fake results. Mitigations to
consider when this becomes a real problem (not v1):

- **Audit trail already exists** — `reported_by_discord_id`, `reported_at`.
- **Admin delete / edit** — `/pod-result-edit <id>` and `/pod-result-delete <id>`
  gated to a server role.
- **Channel visibility** — every submission auto-posts to a #pod-results channel
  so the community can flag falsehoods.
- **Optional confirmation** — bot DMs the reported champion to confirm. Skipped
  for guests (no Discord ID).

Decision deferred until usage shows whether this is needed.

---

## Out of scope for v1

- Match-level pairings or per-game scores (Tier 3).
- Decklist capture / Draftmancer pool ingestion.
- Bonus points into `PlayerSetScore`.
- Bracket generation / running the swiss inside the bot.
- Linking a guest's later `/join` to past pod-draft rows (admin tool, post-v1).

---

## Implementation order (when we pick this up)

1. Migration: `pod_draft_events`, `pod_draft_participants`.
2. `bot/services/pod_drafts.py` — record_event, list_champions, player_pod_stats.
3. `/pod-result` modal + handler.
4. `/champions` + `/pod-stats` reads.
5. `/stats` block augmentation.
6. Tests around the service layer (placement uniqueness, guest handling, set
   nullability, cross-set trophy counting).
7. Frontend integration once the React/Vite slice begins.

Estimated scope: small-to-medium. The shape is constrained enough that the
service layer is straightforward; most of the work is the `/pod-result`
walkthrough UX and getting the moderation story right if/when it's needed.
