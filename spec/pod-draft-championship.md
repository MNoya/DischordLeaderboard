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

## Automation (supersedes the manual Sesh flow)

The championship is **no longer a manually-created Sesh event, and its announcement is no longer a manual paste**. The bot creates and announces it on its own. Everything below this section (detection, auto-applied rules, seeding, crown embed, Swiss/results) is unchanged — the bot-created pod carries "Championship" in its name, so the existing name-based detection and auto-config apply exactly as before.

- **Bot-created.** At the scheduled championship time the bot posts the pod through the same scheduled-card path the weekly slots use (`post_scheduled_card`), named so `is_championship` matches. No human runs a Sesh `/create`.
- **Auto-announced.** The bot sends the announcement itself; the old manual template at `prompts/championship-announcement.md` is superseded. Copy is iterated in code, not mirrored here.
- **Timing rule: the weekend before the incoming set's prerelease.** The championship always lands on the Saturday before the next set's tabletop prerelease window opens. This is encoded as the incoming set's `championship_date` in `UPCOMING_RELEASES` (`bot/services/pod_schedule.py`), which currently drives only the "final week" Monday blurb and must also drive the auto-create.
- **MSH → HOB:** HOB prerelease runs **Aug 7–13, 2026**, so the MSH Set Championship is **Saturday Aug 1, 2026, ~2–3 PM ET**. The HOB entry in `UPCOMING_RELEASES` has no `championship_date` yet; it needs Aug 1 filled in.

Still to design/implement: the exact auto-create trigger (a dated job off `championship_date`, mirroring the weekly card jobs), and the announcement copy + where it posts.

### Prior announcement (reference for the auto-version)

The last championship (SOS) was Sesh-created and used the text below. It is recorded here as the content model the automated announcement should follow; the real copy lives in code and is iterated there. Title in Discord was `🗓️👑 SOS Set Championship`.

```
Closing off Secrets of Strixhaven!
The leaderboard decides who plays for the championship, and the winner is crowned @Set Champion

📊 Standings: https://dischord.pages.dev/leaderboard/SOS
📺 Streamed live: https://twitch.tv/GatoDelFuego

How it works
• RSVP here if you can make it. The eight highest-ranked players who show up take the seats, the rest are alternates for no-shows.
• Best of 3, Swiss, three rounds, one Champion.

Marvel Super Heroes arrives <in a month>
```

What must become dynamic in the auto-version:
- Outgoing set name in the title and the "Closing off …" line (SOS → MSH → …).
- The standings set code in the URL, **and the domain**: the site is now `limitedlevelups.com`, so it is `https://limitedlevelups.com/leaderboard/<SET>`, not the old `dischord.pages.dev` preview.
- The `@Set Champion` role mention and the streamer link.
- The closing "<incoming set> arrives <relative time>" line (Marvel Super Heroes → The Hobbit, with a live countdown to its Arena release).

For MSH → HOB that resolves to: "Closing off Marvel Super Heroes!", standings `…/leaderboard/MSH`, and "The Hobbit arrives <t:…:R>" counting to Aug 11, 2026.

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
:llu: Players ranked by **{set_code} Leaderboard** (linked)
…seated 8…
──────────
Alternates
…rest…
```

The pre-lobby header drops the "Projected" word, leads with the llu emoji, and links the set's leaderboard.
Built at render time (`seeding_phase_projected()`) so the emoji resolves from the live registry.

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
**leaderboard-seated** pods, and random-seated pods are untouched.

**Auto-post for the championship.** Right after the crown registration embed posts, the listener fires one
refresh. For the championship the refresher **auto-creates** the seeding table (so the organizer never has
to post it), then keeps it current through the same projected → live refresh. With zero RSVPs at
registration it posts an explicit placeholder — "Waiting for players to confirm attendance." under a
`Yes (0)` header — so the table is visible immediately and the in-place refresher replaces it as RSVPs and
then connections arrive. Non-championship pods keep the post-on-demand behavior: the refresher only updates
a table that was already posted via `/pod-seeding` or the Seating Table button, never creating one.

**Pinning.** The first seeding table posted is pinned (`finalize_seeding_post` → `_pin_first_seeding_table`).
Later on-demand `/pod-seeding` re-posts stay unpinned and override each other below the anchor — the stale
purge skips pinned messages. The refresher updates *every* seeding table it finds (pinned anchor plus any
on-demand re-post, each gets its own image copy), so the anchor never drifts stale. The Draftmancer lobby
message stays the manager's own separate pin: **two pins** during the draft (lobby + seeding), by choice —
folding the seeding embed into the lobby message was considered and rejected to avoid two updaters
clobbering one message's embeds.

**Spectate relocation.** Right after the manager posts the spectate link, it fires `notify_seeding_repost`
→ `repost_seeding_table`, which *replaces* the table rather than editing it: it clears the scrolled-up
pinned anchor (and any on-demand copies, `include_pinned=True`) and posts a fresh table at the bottom by
the spectate link, then pins that one. So the seeding table follows the action down to the live lobby
instead of staying stranded at the top, and there's still exactly one seeding pin. The spectate link goes up
the moment the bot claims ownership, when the lobby is usually still empty, so for the championship the
re-post falls back to the waiting placeholder (same as registration) rather than posting nothing — it then
fills in as players connect.

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
