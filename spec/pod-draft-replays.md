# Pod Draft — 17lands replay links

Working spec. **Not started.**

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
