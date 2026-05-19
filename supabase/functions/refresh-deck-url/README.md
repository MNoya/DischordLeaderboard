# `refresh-deck-url` Edge Function

Stopgap fix for Discord CDN URL expiration. Called by the frontend when a stored
`pod_draft_participants.deck_screenshot_url` is about to expire (or already has). Calls Discord's
`POST /attachments/refresh-urls`, writes the refreshed URL back to the DB, returns it. Falls back
to the stale URL on any failure so the modal still tries to render.

This is intended to be retired when Cloudflare R2 storage comes online (see `r2-deck-screenshots`
branch). Discord can permanently lose attachments when source messages are deleted; R2 doesn't.

## API

```
POST /functions/v1/refresh-deck-url
Authorization: Bearer <SUPABASE_PUBLISHABLE_KEY>
Content-Type: application/json

{"eventId": "<uuid>", "displayName": "<participant draftmancer name>"}
```

Response: `{"url": "<refreshed-or-current>", "refreshed": true|false}`. `url` is `null` only when
the participant exists but has no stored screenshot.

## Secrets

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are provided by the platform automatically. Set
the third one yourself:

```
supabase secrets set DISCORD_BOT_TOKEN=...
```

(Dashboard alternative: Project Settings → Edge Functions → Secrets.)

The bot token must belong to a bot that's still a member of the guild where the screenshot was
originally posted and has read access to the channel/thread — otherwise Discord refuses to
re-sign the URL and we fall back to the stale value.

## Deploy

### Option A: CLI

```
npm install -g supabase           # or use the standalone install
supabase login
supabase link --project-ref yrecdosksgigpceholjl
supabase secrets set DISCORD_BOT_TOKEN=...
supabase functions deploy refresh-deck-url
```

### Option B: Dashboard

Supabase dashboard → Edge Functions → **Deploy new function** → name `refresh-deck-url` → paste
`index.ts` contents → Deploy. Set the secret under **Settings → Edge Functions → Secrets**.

## Sanity check after deploy

```
curl -X POST \
  -H "Authorization: Bearer $SUPABASE_PUBLISHABLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"eventId":"<known-event-id>","displayName":"<known-participant>"}' \
  https://yrecdosksgigpceholjl.supabase.co/functions/v1/refresh-deck-url
```

Expect `{"url":"https://cdn.discordapp.com/...?ex=...","refreshed":true|false}`.
