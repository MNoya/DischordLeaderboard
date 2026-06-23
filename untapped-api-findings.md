# Untapped.gg API — findings and `/link-untapped` design

Investigation of whether Untapped.gg exposes a parseable API we can pull player data from, and what a `/link-untapped` command would look like alongside the existing 17lands linking. Decision coming out of this: ship linking + enrichment (and optionally a ladder fallback) first; pod integration is parked until Companion adoption is real.

## The endpoint

The profile page (`https://mtga.untapped.gg/profile/{user_id}/{player_id}`) is a Next.js app that hydrates client-side from a clean JSON REST API. The match data comes from:

```
GET https://api.mtga.untapped.gg/api/v1/games/users/{user_id}/players/{player_id}/?card_set={SET}
```

From a profile URL the two path IDs are both **public** (they sit in the browser address bar — no secret token like 17lands):

- `user_id` — Untapped account UUID, e.g. `2a6ab2d5-2d47-4d81-9fc5-8e5188eff756`. One Untapped account.
- `player_id` — the MTGA persistent player ID (the Arena account identity), 16 hex chars, e.g. `44298EC328D1CA4E`.

The path is `users/{uuid}/players/{hex}` because one Untapped account can wrap several linked Arena accounts. They're distinct identities, but for our purposes they always arrive together as one URL path and are only ever used as a pair to build the request — opponents in the match log are keyed by `player_name`, not by the hex, so the Arena ID is not a join key for us. Store the pair as a **single string with the slash** (`{uuid}/{hex}`) — the exact path segment spliced into the URL, 1:1 with what the user pastes.

No auth required (`is_authenticated: false`; the only cookie is a Mixpanel id). Response is `application/json`, gzipped, ~47KB for an active player.

### CORS

`access-control-allow-origin` is locked to `https://mtga.untapped.gg`. That only restricts browser JS on another origin — a server-side fetch (the bot) ignores CORS entirely. If the React app ever needs it live in the browser, proxy through a Cloudflare Pages Function under `functions/api/untapped/...` that re-emits a permissive header; for the bot's refresh path there is nothing to bypass.

### `card_set` is a season window, not a set filter

The param is **required** (400 `"Missing card set"` without it). `card_set=SOS` returned 303 matches spanning `2026-04-21` (exactly when the prior meta-period ends) through today, **across every format played** — Premier, Trad, Sealed, Quick events, Direct games, and Constructed. So it scopes to the season window, not to one set's cards. One GET per active set code pulls the whole season's history in a single response. Valid values are set codes; the active meta-period is described at `https://api.mtga.untapped.gg/api/v1/meta-periods/active`.

Other endpoints seen on the profile page: `api/v1/account/collections/{player_id}?user_id={uuid}` (collection), `api/v1/meta-periods/active` (season windows), and card-tile art at `mtgajson.untapped.gg/art/tiles/64/manifest.json`. The `_next/data/{buildId}/...json` payloads are the UI shell only, not player data.

## Payload shape

A flat JSON **array of matches**, newest-first is *not* guaranteed — sort by `match_start` yourself. Per match (top-level keys):

```
short_id, match_start (epoch ms), event_name, super_format, match_win_condition,
games[], winning_team_id, active_player_id,
friendly_deckstring, friendly_deck_name, friendly_deck_id, friendly_deck_colors, friendly_deck_tile_id,
friendly_team_id, friendly_system_seat_id,
friendly_ranking_* / friendly_mythic_* / friendly_rating_*  (before & after),
friendly_course_wins_before, friendly_course_losses_before,
opponents[]  ({ player_name, team_id })
```

Per entry in `games[]`: `game_number`, `game_duration_seconds`, `winning_team_id`, `friendly_deckstring`, `player_opening_hands`, `opponent_revealed_colors`, `opponent_revealed_archetype`, `opponent_revealed_deckstrings`.

Notes:
- **Win = `winning_team_id == friendly_team_id`**. There is no explicit win/loss flag.
- Cards are Arena **deckstrings** (base64), not names — decode against Untapped's card DB if you want card-level data.
- It's the *match* log. There's no draft-pick data (17lands' strength), and no pre-aggregated winrates — the frontend computes those client-side.
- This is an undocumented private API. No stability or rate-limit guarantees.

## Event taxonomy (`event_name` → format group)

Observed for `card_set=SOS`:

| event_name pattern | maps to |
|---|---|
| `PremierDraft_SOS_*` | Premier |
| `TradDraft_SOS_*` | Traditional |
| `Sealed_SOS_*` | Sealed |
| `ContenderDraft_*`, `PickTwoDraft_*`, `MWM_*` (Midweek Magic), `*JumpIn*`, `*Cascade_BotDraft*` | Quick / event drafts |
| `DirectGameTournamentLimited`, `DirectGameLimited`, `DirectGameBrawl` | **Direct games (community pods)** |
| `Play_Brawl_Historic`, `Historic_Play`, `Historic_Challenge_*`, `Historic_Ladder`, `MWM_StarStandard_*` | Constructed (irrelevant to the limited leaderboard) |

## Use case 1 — Direct/pod games (parked, but the strongest finding)

The community's pod nights show up as `DirectGameTournamentLimited` / `DirectGameLimited`, and they are **Bo3** (`games` length 2–3 = the match played out). They cluster weekly — each date is a pod, ~3 Swiss rounds:

```
2026-05-14   vs NiamhIsTired, Bacchus, WaveofShadow
2026-05-21   vs TripleOWhite, eltonium, zoinks
2026-06-04   vs Narwhalrus, Aristeo, WaveofShadow
```

Each row carries the friendly deck (`friendly_deckstring` + `friendly_deck_id`), the opponent's **Arena name** (`opponents[].player_name`), and the match result. We already store `arena_name` + `arena_aliases` on `Player`, so opponents resolve to community members by name. From one linked player you reconstruct their pod result; from several you can cross-validate a whole bracket. Direct games have `friendly_course_wins_before/losses_before = null` (they aren't laddered events) — consistent with them being pods.

**Decision: parked.** Pod integration relates to the existing `pod_draft_matches` / `pod_draft_replays` / Draftmancer pipeline and that reconciliation is a later design pass. Do not wire pods in the first cut.

## Use case 2 — ladder events from the match log (optional fallback)

Reconstructable. There is no event-instance id (only the format string, shared across every run), but each draft produces a unique `friendly_deck_id`, so **`friendly_deck_id` segments individual draft events**. Per deck_id: final W-L from the last match's result + course progression; trophy when the run reached the win cap. This reimplements what 17lands already gives per-event for free, so Untapped earns its keep on the ladder only as a **fallback for players who run Untapped's Companion but not 17lands**.

## Use case 3 — enrichment (free byproduct)

Opponents, decklists (deckstrings), per-game revealed colors/archetypes, and ranking-tier deltas. Display-only, no scoring risk.

## Prerequisite

Same model as 17lands: the data only exists if the player runs **Untapped's Companion**, uploading their MTGA logs. Community adoption gates the entire feature's value.

## Provisional `/link-untapped` design

Near-clone of `bot/commands/link_17lands.py`:

- **Command** `bot/commands/link_untapped.py` — DM walkthrough, user pastes their Untapped profile URL. Instruction copy points them at Companion → profile → copy the browser URL.
- **Service** `bot/services/untapped.py` — `UntappedClient` mirroring `SeventeenLandsClient`: parse the `{uuid}/{hex}` pair out of the URL (`/profile/(?P<uid>[0-9a-f-]{36})/(?P<pid>[0-9A-F]{16})`), keep it as one string, `verify_profile()` (does the games GET 200?), `fetch_matches(profile, card_set)`.
- **Storage** — one new **nullable** column on `Player`: `untapped_profile`, holding the `{uuid}/{hex}` path segment, parallel to `seventeenlands_token`. Nullable preserves the lightweight-pod-player invariant. The value is public, so no "stored securely" framing needed.
- **Refresh** — one GET per active set code, on the existing tick cadence. For the ladder fallback, segment events by `friendly_deck_id` and feed `draft_events`-shaped rows; for enrichment, persist match rows for the player profile page.

Open decisions deferred: pod reconciliation against the existing pod pipeline, and whether the ladder fallback ships in the first cut or later.
