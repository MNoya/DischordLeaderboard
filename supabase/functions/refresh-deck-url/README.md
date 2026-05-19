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

`SUPABASE_URL` is provided by the platform automatically. Set the other two yourself:

```
supabase secrets set DISCORD_BOT_TOKEN=...
supabase secrets set SERVICE_ROLE_JWT=...    # legacy service_role JWT from dashboard → API Keys → Legacy
```

The auto-injected `SUPABASE_SERVICE_ROLE_KEY` is the new `sb_secret_*` format which PostgREST
doesn't translate to a role claim, so the function falls back to the legacy JWT. The role itself
also needs explicit grants on the table (see migration `a8t9u0v1w2x3`).

The bot token must belong to a bot that's still a member of the guild where the screenshot was
originally posted and has read access to the channel/thread — otherwise Discord refuses to
re-sign the URL and we fall back to the stale value.

## Deploy

```
npm install -g supabase
supabase login                                                          # or set SUPABASE_ACCESS_TOKEN
supabase secrets set DISCORD_BOT_TOKEN=... SERVICE_ROLE_JWT=... --project-ref yrecdosksgigpceholjl
supabase functions deploy refresh-deck-url --project-ref yrecdosksgigpceholjl --no-verify-jwt
```

`--no-verify-jwt` is required: the function is called from the browser with a publishable key
which the gateway rejects as not-a-JWT. The function does its own DB lookup, has no destructive
paths, and the only side-effect of misuse is hitting Discord's rate limit on refresh-urls.

## Sanity check after deploy

```
curl -X POST \
  -H "Authorization: Bearer $SUPABASE_PUBLISHABLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"eventId":"<known-event-id>","displayName":"<known-participant>"}' \
  https://yrecdosksgigpceholjl.supabase.co/functions/v1/refresh-deck-url
```

Expect `{"url":"https://cdn.discordapp.com/...?ex=...","refreshed":true|false}`.
