# Pod Draft — MagicProTools draft log integration

Working spec. **Not started**. Locked design choices captured below so the next session can implement without re-discovery.

## What it does

After `endDraft`, the bot persists the gzipped compact draft log AND posts per-player MagicProTools viewer links as link-buttons on the champion announcement embed. Players click → opens the per-seat draft view at magicprotools.com.

## Reference implementation

Amelas/DraftBot, cloned locally at `~/Projects/Personal/DraftBot`. Key files:

- `helpers/magicprotools_helper.py` — the porting target. `convert_to_magicprotools_format(draft_log, user_id) -> str` turns Draftmancer pick JSON into the MTGO-style text format MagicProTools expects. `submit_to_api(user_id, draft_data) -> str | None` posts to MagicProTools' API.
- `services/draft_setup_manager.py:1075–1140` — how Amelas surfaces the URLs (embed fields, plus a fallback "Import to MagicProTools" path via DO Spaces). They upload the MTGO-format `.txt` to public object storage and use `magicprotools.com/draft/import?url=<public-url>` so MagicProTools can fetch and render the draft itself.

## API details (extracted from Amelas)

- Endpoint: `POST https://magicprotools.com/api/draft/add`
- Headers: `Accept: application/json, text/plain, */*`, `Content-Type: application/x-www-form-urlencoded`, `Referer: https://draftmancer.com`
- Form body: `draft=<MTGO-format text>`, `apiKey=<key>`, `platform=mtgadraft`
- Response: `{ "url": "..." }` on success, `{ "error": "..." }` on failure
- API key required; user needs to obtain `MPT_API_KEY` from MagicProTools

## Design decisions locked

1. **Persist the raw log** on `pod_draft_events.draft_log_gz BYTEA` (~9 KB per pod gzipped via existing `bot/scripts/draftmancer_log.pack`). Keeps the door open for our own future viewer / analytics; doesn't make us dependent on MagicProTools.
2. **Source of MagicProTools URLs**: API call only for v1. If the API call fails for a seat, that seat's button is omitted (graceful degrade — no broken-link buttons). **Fallback path deferred, not skipped**: an `Import to MagicProTools` fallback equivalent to Amelas's is implementable later via Supabase Storage, a Cloudflare Pages function, or a Discord channel attachment — any public HTTP URL works as the `?url=` parameter. Revisit if API failures turn out to matter in practice.
3. **Storage of URLs**: `pod_draft_participants.draft_log_url` — column already exists.
4. **Surface**: link-button row on the champion announcement embed, alongside the existing "Full Thread" button. One button per participant. Discord limits: 25 components / 5 rows / 5 buttons per row. 8-player pod = 9 buttons (1 Full Thread + 8 players) = 2 rows. 10-player = 11 buttons = 3 rows. Well within limits.
5. **Button labels**: champion gets a 🏆 prefix; others plain. Labels are display names from participant rows.

## Implementation steps

1. **Migration** — new alembic revision adding `pod_draft_events.draft_log_gz BYTEA NULL`. Update `bot/models.py` `PodDraftEvent`.
2. **Settings** — add `MPT_API_KEY: SecretStr | None = None` to `bot/config.py`. Read from `MPT_API_KEY` env var.
3. **Port helper** — copy `magicprotools_helper.py` content from Amelas into `bot/services/magicprotools.py`. Strip:
   - DigitalOcean helper imports/calls
   - The fallback `upload_draft_logs` path that uses DO Spaces
   - Keep `convert_to_magicprotools_format` (pure function) and `submit_to_api` (API call).
4. **Persistence hook** — in `bot/services/pod_draft_manager.py:_on_draft_log`, after stashing the log in `self.draft_logs`, also persist a gzipped compact form to `pod_draft_events.draft_log_gz`. Use `bot.scripts.draftmancer_log.build_compact` and `gzip.compress`.
5. **Upload hook** — in `pod_tournament.finalize_tournament` (or during `_announce_or_update_champion` once log is persisted), for each participant, call `submit_to_api(user_id, log)` and stash the URL on `pod_draft_participants.draft_log_url`.
6. **Embed wiring** — extend `bot.services.pod_tournament.build_thread_link_view` (or add a sibling `build_announcement_actions_view`) to emit per-player MPT link buttons. Pass per-participant info to it.
7. **Champion announcement** — call the extended view builder; attach to the announcement embed `send`/`edit`.

## Open questions

- **Button labels with mana emojis?** Could prefix each player's button with their deck-color mana emoji (`:manawu: Elfandor`). Pleasant but maybe busy. Defer; default to plain name + optional 🏆 for champion.
- **What if 17lands-linked but no Player.discord_id?** Draft logs are keyed by Draftmancer user_id, not Discord. The Draftmancer user_id comes from the log itself. The participant's Discord ID is for the button-label / mention layer. Some unlinked participants might still have draft logs — link button would just label as their draftmancer name.
- **Timing**: when in the lifecycle do we upload? At `endDraft` (immediately) vs at `finalize_tournament` (after R3)? Per-seat URLs don't depend on bracket state, so technically uploadable at endDraft. But we have nowhere to show them until the announcement. Recommend: upload at endDraft (1× HTTP per seat, fire-and-forget), populate `draft_log_url`, retrieve when the announcement builds.

## Files to touch

| File | Action |
|---|---|
| `alembic/versions/r*_pod_event_draft_log_gz.py` | new — `pod_draft_events.draft_log_gz BYTEA` |
| `bot/models.py` (`PodDraftEvent`) | add `draft_log_gz` column |
| `bot/config.py` (`Settings`) | add `MPT_API_KEY` |
| `bot/services/magicprotools.py` | new — port of Amelas helper, trimmed |
| `bot/services/pod_draft_manager.py` (`_on_draft_log`) | persist gzipped compact log |
| `bot/services/pod_tournament.py` (`finalize_tournament` and/or `_announce_or_update_champion`) | invoke `submit_to_api`, store URLs |
| `bot/services/pod_tournament.py` (`build_thread_link_view` or sibling) | per-player link buttons |
| `bot/scripts/draftmancer_log.py` | maybe expose `build_compact_gz(log) -> bytes` for direct call from `_on_draft_log` |

## Verification

- Set `MPT_API_KEY` in `.env`.
- Run a real draft (or `!testbracket`-like via testlobby placeholder hook if added).
- After endDraft: `pod_draft_events.draft_log_gz` should be populated; participants' `draft_log_url` should be MagicProTools URLs.
- Click a button on the announcement — opens the per-seat draft view.

## Out of scope (defer to future)

- Our own draft viewer (would replace MagicProTools dependency). Raw log is persisted, so we can build later.
- Pack-1-pick-1 analytics across pods.
- Auto-export to 17lands or other services.
