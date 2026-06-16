# Event schedule from MTG Scribe (handoff)

Shipped `/event-scribe` (commit `655a441`): an on-demand command that pulls the MTG Arena event calendar from mtgscribe.com and renders the in-progress + upcoming Limited schedule, grouped by set. This doc captures how that data layer works and what carries forward into **Format Schedule integration** (Todoist `6gmr6C7Vr3R7qxpj`): proactive announcements of Flashback/Quick Draft rotations, Cube, Qualifiers, etc. in their channels.

## What shipped

| File | Role |
|---|---|
| `bot/services/mtgscribe.py` | REST client for mtgscribe.com + grouping/partition of events. The reusable data layer. |
| `bot/services/scribe_formats.py` | Standalone format short-name map (`Premier Draft` → `Premier`); vendorable, no bot imports. |
| `bot/commands/event_scribe.py` | The `/event-scribe` cog: pipeline, filters, embed render, link button. |
| `bot/commands/testscribe.py` | `!test scribe` owner command — renders synthetic fixtures through the **same** pipeline so it can't drift. |
| `bot/assets/mtg-scribe.png` | 128px logo used as the embed thumbnail (attachment, not emoji). |
| `frontend/public/set-symbols/cube.png` | The CUBE set symbol, generated from the keyrune `pz1` glyph (keyrune has no `cube.svg`). |

## Data source — the REST API, not the RSS feed

`GET https://mtgscribe.com/wp-json/tribe/events/v1/events?start_date=YYYY-MM-DD&per_page=50&page=N`

The Events Calendar (WordPress) REST API. The `/events/feed/` RSS only carries a start date; the REST endpoint carries `utc_start_date`/`utc_end_date`, local `start_date`/`end_date`, `tags`, `categories`, `title`, `slug`. Paginate via `total_pages`; requesting a page past the end returns **404**, so loop on `total_pages`, never on an empty-page sentinel.

### Cache-busting (important)

MTG Scribe's CDN keys on the full query string and serves **stale dates** for the canonical URL — a `Cache-Control: no-cache` header does *not* reach origin, but a unique query param does. `fetch_events` appends `_cb=YYYYMMDDHHMMSS` (per-invocation): every call is a fresh origin fetch. A daily `_cb=YYYYMMDD` bucket was tried first, but it let a stale-date copy (a corrected end date, a duplicate queue) persist on the CDN for the rest of the day. This is an on-demand command that defers, and the origin is only ~0.3s/page slower than the edge cache (~1s extra over the 3-page fetch), so per-invocation freshness is the right trade. If origin load ever matters, a `YYYYMMDDHHMM` (per-minute) bucket keeps repeat calls fast while bounding staleness to a minute.

## The tag taxonomy (the key asset for the next task)

Everything downstream keys off tags, not titles. Observed slugs on **arena** events:

- **Scope**: `arena` (client-playable; tabletop events lack it), `limited` (vs Arena Constructed).
- **Draft families**: `premier-draft`, `traditional-draft`, `quick-draft`, `pick-2-draft`, `remix-draft`, `contender-draft`. (`premier-draft` is broad — also on Cube/Remix/Contender.)
- **Sealed**: `sealed`, `traditional-sealed`.
- **Arena Direct**: `arena-direct` + a booster slug (`play-boosters` / `collector-booster`) + sometimes `japanese-language-box`.
- **Midweek**: `midweek-magic` + the real format tag (`quick-draft`, `phantom`+`sealed`, `cascade`+`draft`, `brawl`, `momir`, `pauper`, …). Many Midweeks are Constructed (no `limited`).
- **Competitive**: `play-in`, `qualifier`, `arena-championship`, `arena-limited-championship-qualifier`. Most ACQ Play-Ins are Constructed (Standard/Pioneer/Historic) and get dropped by the Limited scope; the Sealed ones survive.
- **`flashback`** — marks old-set rerun drafts (Strixhaven, Bloomburrow, Aetherdrift, War of the Spark…). **Directly answers "announce Flashback rotations."** 9 such events were present over a 90-day window.
- **Set tag**: the slugified set name (`secrets-of-strixhaven`, `marvel-super-heroes`). Maps back to `bot/sets.py` via `_slugify(seed.name)`.

## Pipeline (event_scribe.process_events — the one place both command and test route through)

`fetch_events` (arena scope only) → `normalize_event` → filter (`_in_scope` + `_passes_format` + `_passes_set`) → `group_events` (day-based key) → `partition_by_now` → horizon trim (unfiltered only).

- **`normalize_event`** repairs labels that the generic `"<format>: <set>"` title split gets wrong:
  - *Arena Direct* (`Arena Direct: <set> <product>`) → set from tags, format `Arena Direct Play`/`Collector`.
  - *Midweek* → set-bearing groups under the set with the real trailing format; set-less/crossover (a `+` in the label) groups under a generic `Midweek Magic` header, shown verbatim.
  - *Competitive* → keeps the `Bo1`/`Bo3` differentiator parsed from the title.
  - All others → `_clean_set_label` collapses a set name buried in qualifier words (`Sealed Marvel Super Heroes Bo3` → `Marvel Super Heroes`).
- **`group_events`** keys on `(set, start_date, end_date)` — **calendar dates, not timestamps** — so queues opening an hour apart still merge into one line.
- **`partition_by_now`** sorts in-progress by latest end first, upcoming by soonest start.
- **Horizon**: the unfiltered view drops upcoming past `UPCOMING_HORIZON` (45 days); any explicit filter shows everything it matches. No hard line cap.

## Rendering conventions (so announcements match the command's voice)

- Markdown header `###` for the title and each section; sets are `**bold**` with their `:code:` emoji prefix; queues are `└`/`├` tree lines (NBSP-padded: ` ├  `).
- Emoji resolve **by name** at runtime from `bot.fetch_application_emojis()` — no hardcoded IDs. Names: `mtga` (title), `scribe` (link button), `cube`/`<setcode>` (set), `8000gems` (collector), `arenachamp` (replaces the literal "Arena Championship"); `📦` is the unicode package for Play boosters.
- Date range: same month `June 2–8`, cross-month `May 26–June 1`. Relative countdowns use Discord `<t:…:R>`.
- `>3` merged formats → `Premier, Trad Draft and others` (priority via `FORMAT_PRIORITY`).
- **Rosters** collapse formats that rotate one-set-per-window so they don't scatter a header per set: `🪦 Flashback` (any section, from the `flashback` tag) and `🤖 Quick Draft` (Coming Up only — the in-progress Quick Draft stays under its set). Each roster lists its sets as tree lines with the set logo, date range, and countdown. See `_section_blocks` / `_roster_block`.
- **Set-name fit** (`_fit_set_name`): a roster line that would wrap shortens the set name — full name → name minus colon-subtitle and leading article → set code — taking the first that fits the estimated width (`ROSTER_LINE_MAX_WIDTH`, with the custom emoji and `<t::R>` countdown approximated since they render shorter than their source). "Duskmourn: House of Horror" → "Duskmourn"; "The Lost Caverns of Ixalan" (cross-month) → "LCI".
- **Midweek is always called out**: set-bearing Midweeks keep a `Midweek` prefix on the format under their set header (`Midweek Phantom Sealed`), so a Midweek never reads as a regular queue.
- **Cube logo by tag**: any event with a `cube`/`*-cube` tag resolves the `cube` emoji regardless of its name, so oddly-named cubes ("Some Kind of new Cube") still get the logo.

## Deploy / ops

- **`!sync` required** — `/event-scribe` has a `format` choice list and a `set` autocomplete option.
- **Upload application emojis** by exact name: `mtga`, `scribe`, `cube`, `8000gems`, `arenachamp` (set symbols optional; lines render without them).
- Source symbols for emoji live in `frontend/public/set-symbols/<code>.png`.

## Known gaps (not blockers)

- `/event-scribe` is not listed in `/help`.
- No unit tests; `normalize_event`, the filters, day-grouping, the roster fit (`_fit_set_name`), and the "and others" wording are pure functions and good table-driven candidates. `!test scribe` fixtures exercise the roster/midweek/cube/shortening paths end to end.
- Set-bearing Midweeks still group under their set header (now `Midweek`-prefixed) rather than all under one "Midweek Magic" block, consistent with global set-grouping.

---

## Next: Format Schedule integration

**Goal**: the bot proactively announces rotations from Scribe's calendar — Flashback & Quick Draft rotations in the flashback channel, plus Cube, Qualifiers, etc. (Todoist describes "read the once-per-set WotC article"; Scribe already structures that data, so consume Scribe rather than parsing WotC prose.)

**Reuse, don't rebuild**: `mtgscribe.fetch_events` + the tag taxonomy + `normalize_event` labels + `render`-style formatting. The announcement copy should share builders with `/event-scribe` so they can't drift (same lesson as `testscribe`).

**To build**:
- A scheduled tick (model on `bot/tasks/pod_schedule_post.py` + `bot/services/pod_schedule.py`, which already own the weekly-post + `SCHEDULE_TZ` pattern) that detects events **starting** on a given day and posts an announcement.
- Selection: filter by tag — `flashback`, `quick-draft`, cube (`powered-cube`/`arena-cube`), `competitive` tags — to decide *what* to announce and *which channel*.
- Channel routing: a config map (tag/category → channel id), e.g. a flashback channel. Add to `bot/config.py` (Discord fields are optional there).
- Dedup: track what's been announced (a small table keyed on `seventeenlands_event_id`-equivalent — here the Scribe event `id` or `slug`) so a restart or daily tick doesn't repost. `leaderboard_messages` is the precedent for "track what we posted."

**Open questions for the owner**:
- Which channels for which event types (flashback vs quick-draft vs cube vs qualifier)?
- Announce on the day each event *starts*, or a digest at set rotation?
- Include in-client Constructed rotations (Standard/Alchemy) or Limited-only?
