# Pod Draft — Set Championship automation

The once-a-format season closer: a single 8-person pod whose seats go to the top of the active-set
leaderboard among whoever is available. This spec covers detecting a championship pod, auto-applying its
rules, naming its Draftmancer session, the standings-priority seeding, and the announcement that opens it.

Everything downstream of "8 players are seated" (Swiss, result reporting, champion finalization, standings,
draft recap) is the existing `pod_tournament` flow, unchanged. The championship is not a new event type —
it is a normal `PodDraftEvent` that the bot recognizes by name and configures for us.

## What this is (and isn't)

- **One pod, eight seats.** No multi-pod split, no "everyone can join." The cut is the top 8 of the active
  leaderboard among those available.
- **Open lobby, kick to enforce.** The Draftmancer link is the normal public pod link. Presence does not
  entitle a seat — the seeding embed shows who is above and below the cut, and the organizer kicks down to
  the qualified 8. Unranked walk-ins sort to the bottom automatically.
- **Guaranteed 8.** The under-fill / fewer-than-8 case is out of scope.

## Detection

A pod is the championship when its name contains `"championship"` (case-insensitive). One helper in
`bot/services/pod_drafts.py` is the single source of truth:

```python
def is_championship(name: str | None) -> bool:
    return bool(name) and "championship" in name.lower()
```

Read from `parsed.name` (the Sesh title, identical to the thread name). No new column — it is always
derivable from the stored event name.

## Auto-applied rules (at `record_event`)

When `is_championship(parsed.name)`:

| Setting | Normal default | Championship |
|---|---|---|
| Format | active set | active set (unchanged — already correct) |
| Pairings (`pairing_mode`) | `swiss` | `swiss` (unchanged — already the default) |
| Seats (`seating_mode`) | `random` | **`leaderboard`** |

So the only rule that actually flips is **seating → leaderboard**. That single flip also activates the
8-seat cap (`CHAMPIONSHIP_CUT`) and the presence-honoring draft-time cut, both of which already live in the
leaderboard-seating path. The organizer can still override any of these through the lobby Settings panel.

## Draftmancer session name

`_build_draftmancer_session` uses a fixed base for the championship instead of `#N` / Month-Day, then falls
through to the existing collision loop (so a re-created lobby gets `-A`, `-B`, …):

```
LLU-SOS-Championship          # first
LLU-SOS-Championship-A        # re-create
LLU-SOS-Championship-B
```

Player-facing URL stays clean: `https://draftmancer.com/?session=LLU-SOS-Championship`. The long thread name
never reaches the session id. (The public recap URL is still `/pods/{slugify(name)}` — long but descriptive;
left as-is.)

## Registration embed (the "Pod Draft registered!" post)

`build_registered_embed` takes the championship flag and swaps to a crowned variant. **Wordings to refine:**

Normal (unchanged):
```
🤖 Pod Draft registered!
Format: **{format}** · Pairings: **{pairings}** · Seats: **{seats}**
Draftmancer link will be posted 10 minutes before the event starts.
```

Championship (`{set_full_name}` is the set's full name from `bot/sets.py`, e.g. "Secrets of Strixhaven"):
```
👑 Set Championship registered!
{set_full_name} Season! Eight seats to the highest-ranked players who claim them.
Format: **{format}** · Pairings: **Swiss Tournament** · Seats: **Leaderboard**
Draftmancer link will be posted 10 minutes before the event starts.
```

A log line records that championship auto-config fired:
```
[CHAMPIONSHIP] auto-config event={event_id} name="{name}" → seats=leaderboard session={session_id}
```

## Seeding — two phases, one embed

The seeding cut runs in leaderboard mode and has two phases. The embed states which phase produced it with a
one-line headline. **Wordings to refine:**

**Phase 1 — before the lobby (no live Draftmancer session).** Cut the RSVP'd Yes list by leaderboard rank,
top 8 seated, the rest are alternates below the divider. (This is the one behavior change: leaderboard mode
currently fills the projected pool in RSVP arrival order — it should rank-order it.)

```
🔮 Projected · Available players, ranked by {set_code} Leaderboard
…seated 8…
──────────
Alternates
…rest…
```

**Phase 2 — lobby is up.** The connected Draftmancer players are the pool, rank-sorted, top 8 seated, anyone
over the cap shown below the divider as kick candidates.

```
🟢 Live · connected to Draftmancer
…seated 8…
──────────
Past the cut
…rest…
```

Presence beats a stale Yes automatically: a Yes who never connects simply isn't in the Phase-2 pool, so the
next-ranked alternate the organizer adds takes the seat. Unranked walk-ins trail to the bottom and fall
below the cut whenever 8 ranked players are present.

**Live refresh.** Once a seeding table has been posted (via `/pod-seeding` or the Seating Table button), it
edits itself in place as the pool changes, in both phases:

- **Projected (pre-lobby):** the sesh listener's `on_raw_message_edit` fires whenever Sesh re-renders its
  RSVP embed, so the table tracks RSVP changes before the draft.
- **Live (lobby up):** the manager's `sessionUsers` handler fires on every Draftmancer join/leave.

Both route through `notify_seeding_change` → a `set_seeding_refresh_hook` callback the command layer
registers (so the service/listener layers don't import the command module). The refresher only acts on
**leaderboard-seated** pods and only edits a table that already exists — it never auto-creates one, and
random-seated pods are untouched.

## The announcement

The full season-closer promo (rules, links, stream) is **kept out of code for now** — it lives as a
paste-ready template at `prompts/championship-announcement.md` that the owner fills in and posts by hand.
The wording (top-8-by-standing entry, set-scoped standings link, stream link, both `<>`-wrapped) is in
that file.

`bot/services/pod_schedule.py` keeps its existing thin **championship-week** auto-blurb (`MSG_CHAMPIONSHIP_WEEK`,
now 👑) through the Monday ghostwrite flow — "final week, pods paused, next set arrives" — which points
people at the manually-posted promo. The rich promo is not auto-composed or auto-posted this round.

### Creating the event

The championship Sesh event is **created manually for now** — no auto-emitted `/create` block, no
hardcoded date. The only requirement is that the title contains "Championship" (case-insensitive), e.g.
`SOS Dischord Community Championship Pod Draft`, so `is_championship` fires and the auto-config applies.
Championship week still emits no normal `/create` blocks (regular pods are paused).

## Alignment check

The pieces reference one fact — the leaderboard standings — and one entry rule, stated consistently:

| Surface | Says | Backed by |
|---|---|---|
| Announcement (manual .md) | "the eight highest-ranked players who show up" | the Phase-1/Phase-2 cut |
| Sesh event (manual) | title carries "Championship" | triggers `is_championship` |
| Registration embed | "highest-ranked players who claim them", Seats: Leaderboard | the `seating_mode` flip |
| Seeding embed | projected-by-standing → live-by-connection | `CHAMPIONSHIP_CUT` = 8 |
| Crown emoji 👑 | announcement + registration embed | distinct from the per-pod 🏆 |

Trophy 🏆 stays the per-pod champion marker (announcement post, deck-reminder copy); the crown 👑 marks the
season championship so the two never blur.

## Config / constants

No `config.py` additions, no model changes, no new tables or columns — championship status is derived from
the event name. The announcement copy (incl. the stream link) lives in `prompts/championship-announcement.md`,
not in code.

## Preview — `!test championship`

A one-fire-per-set effort, so the headlines and cut are verified by eye before the real event rather than
locked down with assertions. An owner-only `!test championship` prefix subcommand renders the seeding embed
in both phases against a placeholder roster (reuse the `testlobby` fixture names, ~10 so the 8-cut and the
alternates/over-cap group both show):

- **Phase 1** — `build_seeding_image_message_from_names(fixture_yes, seat_cap=CHAMPIONSHIP_CUT)` with the
  `🔮 Projected · …` headline.
- **Phase 2** — same builder, `🟢 Live · …` headline, to eyeball the over-cap kick group.

Uses the same embed builder `/pod-seeding` calls, per the testlobby-mirrors-production rule — the preview
shares the string/embed code, owning only the fixture roster. This is the surface for refining the headline
wording, which is still tentative.

## Testing

Minimal by design — this fires once per set and the real risk is unclear copy, which is verified manually
via `!test championship` and a dry-run Sesh event. Two cheap guards worth keeping:

- `is_championship` — substring match, case-insensitive, None-safe.
- `_build_draftmancer_session` — championship base + collision suffixing.

Everything else (seating flip, announcement composition, phase headlines) is verified by eye, not asserted.

## Out of scope

- Multi-pod split for 9+ qualified players.
- Under-fill / fewer-than-8 handling.
- Auto-kicking non-qualified walk-ins (the bot surfaces the cut; the organizer kicks).
- Bot-native signup replacing Sesh RSVP.
</content>
</invoke>
