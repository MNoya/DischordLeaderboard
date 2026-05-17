# Pod Draft — Champion deck screenshots

Working spec for capturing post-pod deck screenshots and surfacing the champion's image on the announcement embed.

## What's already shipped (local DB)

- **Migration** — `alembic/versions/q7g8h9i0j1k2_pod_participant_deck_screenshot.py` adds `pod_draft_participants.deck_screenshot_url VARCHAR NULL` and `deck_screenshot_caption VARCHAR NULL` in one revision. Applied to local; **not yet applied to prod**.
- **Model** — `pod_draft_participants.deck_screenshot_url` + `deck_screenshot_caption` on `bot/models.py`.
- **Service helper** — `bot.services.pod_drafts.capture_first_deck_screenshot(session, discord_thread_id, discord_id, image_url) -> str | None`. First-write-wins per participant. Returns `event_id` on a fresh capture, `None` otherwise.
- **Listener** — `bot/listeners/pod_screenshots.py`. On image attachments in a pod thread by a participant, calls the helper, then:
  - Looks up manager via `ACTIVE_POD_MANAGERS[event_id]`
  - Calls `_announce_or_update_champion(manager)` to refresh the embed
  - If `discord_id in manager.champion_discord_ids`: `message.add_reaction("🏆")`
- **Listener registration** — wired in `bot/main.py` via `setup_pod_screenshots(bot)` next to the existing sesh listener.
- **Champion discord-id set on manager** — `PodDraftManager.champion_discord_ids: set[str]`. Populated inside `_announce_or_update_champion` by filtering the existing `_load_dm_info_sync` result by champion normalized names. **Single source** — reuses the existing `participant_dm_info` query.

## What's NOT yet shipped — STOP/RESUME POINT

- **Prod migration**: `alembic upgrade head` against prod Supabase. Local-only today.

## Just shipped (resume session)

- **Loader extension**: `_load_event_deck_colors_sync` renamed to `_load_event_deck_data_sync`, returns `dict[str, ParticipantDeckData(colors, screenshot_url)]`. One DB roundtrip for both fields. Tiny `_colors_only()` helper unpacks the colors dict for callers that don't need the URL.
- **Embed image injection**: `build_champion_announcement_embed` gained a `champion_screenshot_url: str | None = None` kwarg. When set, calls `embed.set_image(url=...)`. Kwarg pattern chosen over a wider signature change so the thread-side `build_champion_embed` (which doesn't surface screenshots) stays focused on `player_colors=`.
- **Caller wiring**: `_announce_or_update_champion` picks `champions[0]` (rank-1, since standings are pre-sorted) and threads its screenshot URL into the embed. Multi-champion case: only rank-1's image is surfaced (per design decision #5).
- **Testlobby placeholder**: new `_TestlobbyScreenshotListener` cog. When the bot owner uploads an image in a channel that hosts a registered testlobby bracket (matched by `standings_message.channel.id` or `champion_announcement_message.channel.id`), the URL is stashed at `state["screenshots"][_norm(_INVOKER_SEAT)]` and a champion-refresh fires. Testlobby's `_maybe_announce_or_update_test_champion` reads the same key.

## Design decisions locked

1. **Trigger**: first image attachment by any participant in the pod thread (`message.attachments` filtered to `content_type.startswith("image/")`). First-write-wins per participant — re-uploads ignored.
2. **Storage**: just the Discord CDN URL on `pod_draft_participants.deck_screenshot_url`. No re-hosting / re-uploading. Accept the (small) risk that a deleted source message orphans the URL.
3. **Scope**: store for ALL participants, not just champions. Only the champion's URL is surfaced on the announcement embed; the rest sit in the DB for future use (per-player profile pages, etc.).
4. **🏆 reaction**: only on the champion(s)' screenshot message. Determined via `manager.champion_discord_ids`.
5. **Multi-champion case**: rank-1's image goes in `embed.image=`. Others stay in DB but aren't surfaced on this embed (no `embed.thumbnail=` fallback for now — keep simple, revisit if 10-player co-champions become common).
6. **Live update**: the listener fires `_announce_or_update_champion` after every capture, so the embed pulls the new image automatically.

## Open question — RESOLVED

Hybrid of the two options in the original spec:

- Loader side: extend (renamed `_load_event_deck_data_sync`) so one query carries both colors and screenshot URL.
- Embed side: keep `player_colors=` as-is for both embed builders; add a focused `champion_screenshot_url=` kwarg only to `build_champion_announcement_embed` (the one embed that actually surfaces the image).

Rationale: full pure-rename of `player_colors=` → `player_deck_data=` would also touch `build_champion_embed`, which never surfaces screenshots — wider API change for no benefit. The hybrid gives us loader dedup *and* minimal builder churn.

## Files touched / to touch

| File | Status |
|---|---|
| `alembic/versions/q7g8h9i0j1k2_pod_participant_deck_screenshot.py` (url + caption squashed) | ✅ written, applied local |
| `bot/models.py` (PodDraftParticipant) | ✅ |
| `bot/services/pod_drafts.py` (`capture_first_deck_screenshot`) | ✅ |
| `bot/services/pod_tournament.py` (`PodDraftManager.champion_discord_ids` populated in `_announce_or_update_champion`) | ✅ |
| `bot/services/pod_draft_manager.py` (`champion_discord_ids` field) | ✅ |
| `bot/listeners/pod_screenshots.py` | ✅ |
| `bot/main.py` (register listener) | ✅ |
| `bot/services/pod_tournament.py` (embed image injection in `build_champion_announcement_embed`) | ✅ |
| `bot/services/pod_tournament.py` (loader extension `_load_event_deck_data_sync`) | ✅ |
| `bot/commands/testlobby.py` (placeholder image hook for invoker) | ✅ |
| Prod migration apply | ⏳ pending |

## Verification

- `!testlobby round3` → drive R3 → upload an image in the same channel → bot should react 🏆 if you're the champion seat AND the announcement is up.
- `.venv/bin/pytest bot/tests/` — currently 221 passing; should remain.
