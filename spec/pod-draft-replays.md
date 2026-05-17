# Pod Draft — 17lands replay links

Working spec. Branch `pod-draft-replays` (stacked on `pod-draft-magicprotools`).

## Local dev setup

```bash
# 1. Local docker postgres (one-time)
docker start dischord-pg

# 2. Seed real Pod #3 into local docker (needs prod URL once to pull WaveofShadow's token)
SUPABASE_DB_URL=$(grep '^SUPABASE_DB_URL=' .env.supabase | cut -d= -f2-) \
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord \
.venv/bin/python -m bot.scripts.seed_pod3_for_replays
# 14 replay rows: Noya R1✓ R3✓ (R2 skipped from 17lands sync gap), Wave R3✓ (R1/R2 sparse).

# 3. Dev-only PostgREST-shaped proxy in front of docker postgres
DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord \
.venv/bin/python -m bot.scripts.local_supabase_proxy

# 4. Frontend (frontend/.env.local already points to http://localhost:3001)
cd frontend && npm run dev
# http://localhost:5173/leaderboard/pod/sos-pod-draft-3
```

The proxy echoes `Access-Control-Request-Headers` back as `Access-Control-Allow-Headers` so `supabase-js` headers like `accept-profile` and `x-retry-count` clear the CORS preflight.

## What's shipped on this branch

- `pod_draft_replays` table (migration `u2n3o4p5q6r7`) — one row per player per 17lands game record. `(event_id, player_id, game_id)` unique. Indexes on `(event_id, player_id)` and `(event_id, game_time)`.
- `seventeenlands.fetch_user_games(token)` — calls `https://www.17lands.com/data/user_game_list/<token>`. Returns the `games` list (or empty on failure).
- `pod_replays.attribute_games_to_rounds(...)` — score-pattern + time-window attribution. Per-round eligibility bounded by `(prev_match.reported_at, this_match.reported_at]`. Requires exact game count + W/L pattern match; otherwise leaves the round unattributed.
- `pod_replays.fetch_and_persist_replays_for_player(...)` — orchestrator. Fire-and-forget safe.
- Auto-trigger: in `_handle_result_submission`, after an R3 result lands, fires fetch+persist for both players in that match (per the "Only fetch player game history once their last match is reported" decision).
- Public views (migration `v3o4p5q6r7s8`): `public_pod_draft_replays` + `public_pod_draft_event_matches`, granted to `anon`.
- Frontend `/leaderboard/pod/:slug` route → `PodPage.tsx` — raw validation page. Per-player game tables + head-to-head pairings detected via timestamp (±2 min) + turn-count + opposite-result join.
- Replays button on the announcement now uses `settings.public_site_url` so the URL is `dischord.pages.dev/leaderboard/pod/<slug>` (was a bare `/pod/<slug>` that would have 404'd).

## Empirical findings — May 14 Pod #3 trial

- **17lands `game_id` is PER-USER, not per-game.** Confirmed by pulling WaveofShadow's token from prod and comparing her game IDs against Noya's — zero overlap despite playing each other in R3. The cross-player join MUST be by timestamp + turn-count, not game_id.
- **17lands ingestion drops games.** Noya had 8 of 9 expected games; WaveofShadow had 6 of 8 expected. The algorithm degrades gracefully — unmatched rounds stay `inferred_round = NULL`, but the rest still attribute.
- **Misload restarts**: rare but real; filter games with `turns < 3`.

## Decisions locked in this iteration

- Replaced the original `pod_draft_matches.replay_url_a/b` design — that migration never shipped (cleanly removed from the branch history). The per-match approach was too narrow: 17lands lossiness + missing opponent identity make per-side URL attribution unreliable. The flat per-player table is the right shape.
- Skipping the "Find Replays" manual button for now. Auto-trigger fires after R3 results, which lag the games themselves by ~minutes-to-hours of round play, giving 17lands ingestion time to catch up. Revisit if observed lag is too high.
- testlobby champion-state stub for `pod_draft_replays` rows — deferred. Validation seed script (`bot/scripts/seed_pod3_for_replays.py`) populates the real Pod #3 from prod tokens, which is sufficient for now.

## Next design pass — pod-draft layout for the frontend

The current `PodPage.tsx` is raw HTML for data validation. Future design work (separate task):

- **Table-seating order**: render the 8 (or N) players around a virtual round table in actual draft seat order (left → pass-direction), not alphabetical.
- **Deck-color glyphs above player names**: small mana-emoji pips per player, sourced from `pod_draft_participants.deck_colors`.
- **Match cards**: per round, show each pairing as a card with both players' avatars, final score, and the replay links in their natural pair grouping (G1/G2/G3 of the bo3).
- **Head-to-head linking**: when both sides of a game are available, show a single "View this game" link surfacing both perspectives (Noya's POV / Wave's POV) on the 17lands viewer.
- **Trophy/podium decoration** for ranks 1/2/3.

## Original spec below ↓

## What it does

For 17lands-linked participants, surface a "Find Replays" button on the championship announcement. Clicking it queries each linked player's recent 17lands games, matches them to `pod_draft_matches` rows, stashes replay URLs, and posts a "Replays available" message in the thread with per-match deep-links.

Highest value on the trophy match (the 3-0 deciding game), but the approach covers every match in the pod for free.

## 17lands API

- Endpoint: `https://www.17lands.com/data/user_game_list/<token>`
- Returns the user's last 100 games. Each record:
  ```json
  {
    "account_name": "",
    "event_name": "DirectGameTournamentLimited",
    "game_time": "2026-05-14 00:50",
    "link": "/user/game_replay/20260514/<game-id>/<index>",
    "on_play": false,
    "turns": 10,
    "won": false
  }
  ```
- Pod-draft matches register as `event_name == "DirectGameTournamentLimited"`.
- Replay URL = `https://www.17lands.com` + the `link` field.

## Design decisions locked

1. **Trigger: lazy, on demand**. A "Find Replays" button on the championship announcement embed. No automatic background fetching. Reasons: (a) avoids wasted API calls for pods nobody watches; (b) 17lands ingestion has lag — letting the user click means they probably waited long enough.
2. **Bulk fetch per click**. For every 17lands-linked participant, fetch their user_game_list (one HTTP call, returns 100 games). Match games to the event's `pod_draft_matches` by:
   - `event_name == "DirectGameTournamentLimited"` filter
   - Time proximity to `pod_draft_matches.reported_at` (or `pod_draft_event.event_time + offset`)
   - Cross-reference winner/loser to identify which `pod_draft_match` row each replay belongs to
3. **Storage**: per-match URLs on `pod_draft_matches.replay_url_a VARCHAR`, `pod_draft_matches.replay_url_b VARCHAR`. One side may be `NULL` (only one of the two players linked to 17lands).
4. **Idempotent**. Re-clicking the button just re-fetches and overwrites; safe to repeat. Useful when ingestion lag means some replays aren't available yet on first click.
5. **Display**: posts a "Replays available" message in the thread after fetch. One line per pod_draft_match with player names + per-side replay links (or just one if only one player is linked). Does **not** modify the championship announcement.

## Implementation steps

1. **Migration** — add `replay_url_a VARCHAR NULL`, `replay_url_b VARCHAR NULL` to `pod_draft_matches`. Update model.
2. **17lands service** — extend `bot/services/seventeenlands.py` (or new `bot/services/seventeenlands_replays.py`) with `fetch_user_games(token: str) -> list[dict]`. Mind the rate limits (17lands doesn't publish them — reasonable to assume 1 req/sec OK for low volume).
3. **Match algorithm** — for each fetched game record:
   - Filter to `event_name == "DirectGameTournamentLimited"`
   - Parse `game_time` (timezone-naive in their response — likely UTC; double-check on first run)
   - For each `pod_draft_match` row in the event whose `reported_at` is close to the game time and whose `winner_name/loser_name` matches the player's seat: store the replay URL on the right column
4. **Button** — add a `Find Replays` interaction button to the championship announcement's view alongside the existing `Full Thread` link button. Owner-only? Anyone? Defer; recommend anyone for now.
5. **Click handler** — async:
   - Load all participants for this event with linked Players (filter to those with non-null `seventeenlands_token`)
   - For each, `fetch_user_games(token)` → filter + match → write URLs
   - After all done, post the "Replays available" message in the thread with assembled links
   - Edit the message (or re-post idempotently) on re-click
6. **Idempotency**: track the replays-message ID somewhere (manager in-memory is fine since this is best-effort). On re-click, edit the existing message instead of re-posting.

## Open questions

- **Match-game matching**: 17lands user_game_list returns single games, not matches. A pod_draft_match is best-of-3, so we'll see 2–3 game rows per pod_draft_match per player. Decision: link to the *first* game of the match (or simply join all game URLs into a "Replays" list — let the user pick which game to watch). Recommendation: store one URL per side (the first game) plus expose all games as a fallback.
- **Permissions**: who can click "Find Replays"? Recommend anyone in the thread for now. Could lock to admin if rate-limit concerns emerge.
- **Time-window for matching**: how lenient should the game_time vs pod_draft_match.reported_at comparison be? A typical match runs 10–25 minutes. Recommend ±60 min window from `pod_draft_event.event_time`, then within that window match by winner+loser names. If both players are 17lands-linked, the matching is unambiguous; if only one is, time proximity is the main signal.
- **Caching**: do we expire replay URLs? 17lands replay URLs are stable (date-keyed). No expiry needed; we can save them forever.

## Files to touch

| File | Action |
|---|---|
| `alembic/versions/s*_pod_match_replay_urls.py` | new — replay_url_a/_b columns |
| `bot/models.py` (`PodDraftMatch`) | add replay_url_a/_b |
| `bot/services/seventeenlands.py` or new module | `fetch_user_games(token)` |
| `bot/services/pod_tournament.py` | extend announcement view with `Find Replays` button + click handler |
| `bot/services/pod_drafts.py` (or service module) | match-and-store algorithm |

## Verification

- Manually fetch `https://www.17lands.com/data/user_game_list/<your-token>` to confirm response shape.
- Run a real pod with at least one 17lands-linked player → check after click that `pod_draft_matches.replay_url_a/_b` are populated for that player.
- Click the URL — should open the 17lands replay viewer.

## Out of scope (defer)

- Automatic background fetch / retry on ingestion lag.
- Replay archive / browse-by-pod UI on the frontend.
- Cross-referencing the deck-color signal (e.g., "winners in this pod were 80% WR") — separate analytics work.
