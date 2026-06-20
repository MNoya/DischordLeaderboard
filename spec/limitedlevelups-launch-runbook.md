# limitedlevelups.com cutover runbook

Operator runbook for promoting **limitedlevelups.com** to the canonical production domain and demoting **dischord.pages.dev** to a redirect, while keeping feature-branch previews on `*.dischord.pages.dev`. Designed to run "at will" in a low-traffic window. Downtime budget is ~1-2h but the real impact is near-zero because limitedlevelups.com is already live serving content.

## Current state (verified 2026-06-20 via CF API)

Two Cloudflare accounts, two Pages projects, one shared repo. Background: [[reference-cloudflare-two-account-setup]], [[project-llu-launch-plan]].

| | **dischord** | **limitedlevelups** |
|---|---|---|
| CF account | martinnoya@gmail.com (`1dfcb9afa155d3fd842236895f8cfd9a`) | chordocoach@gmail.com (`a704af6840efc2087f25a52c191b4e66`) |
| Source | git-connected (GitHub) | direct upload |
| Production branch | `master` | `dev` |
| Domains | `dischord.pages.dev` | `limitedlevelups.pages.dev`, `limitedlevelups.com` |
| Deploy trigger | CF native build on push to `master` | `.github/workflows/deploy-pages.yml` on push to `dev` → `wrangler pages deploy --branch=dev` |
| Role today | The live public site | Internal preview built with Alex (Tier List / Episodes / Home) |

Other moving parts:
- **Bot links** — `bot/config.py` `public_site_url` defaults to `https://dischord.pages.dev` with no prod env override, so the bot emits dischord links in the leaderboard footer, pod URLs (`pod_tournament.py`, `pod_draft_manager.py`, `leaderboard.py`), and championship posts.
- **Self-referencing SEO** — `functions/_middleware.ts` (canonical tag) and `functions/sitemap.xml.ts` both build URLs from `url.origin`, so each domain currently self-canonicalizes. After cutover only limitedlevelups.com should be canonical; dischord must 301 away to avoid duplicate-content.
- **Hardcoded dischord URLs** — `README.md`, `prompts/championship-announcement.md`, `CLAUDE.md` (line 10 note), and several `spec/*` docs.

## Target state

- **limitedlevelups.com** — canonical production site, fed by **master** (same codebase that feeds the bot).
- **dischord.pages.dev** production — 301/302 → `https://limitedlevelups.com<path><query>`.
- **`<branch>.dischord.pages.dev`** previews — keep serving real content (NOT redirected), so the feature-branch preview workflow survives.
- **Bot** — emits `limitedlevelups.com` links; old dischord links in Discord history redirect automatically.

## Key design decisions

**Redirect lives in app middleware, gated on exact hostname.** `dischord.pages.dev` sits on Cloudflare's own `pages.dev` zone, which we don't control, so zone-level Redirect Rules are not available. The only lever is a Pages Function. Add a guard at the top of `functions/_middleware.ts`:

```ts
if (url.hostname === "dischord.pages.dev") {
  return Response.redirect(`https://limitedlevelups.com${url.pathname}${url.search}`, 302);
}
```

Why exact-match hostname: the production deploy is served at `dischord.pages.dev`, but previews are served at `<branch>.dischord.pages.dev` and `<hash>.dischord.pages.dev`, which do not match — so previews still serve real content. `limitedlevelups.com` / `limitedlevelups.pages.dev` never match either, so there is no redirect loop. The same middleware ships to both projects from master and is a no-op on the limitedlevelups side.

**302 first, promote to 301 later.** Browsers cache 301s aggressively; an early mistake is hard to undo. Ship `302` (temporary), confirm everything is stable for 24-48h, then change the literal to `301` (permanent) so search engines transfer ranking. Both are one-character edits + redeploy.

**limitedlevelups production branch moves dev → master.** A wrangler `pages deploy` is a *production* deploy only when `--branch` equals the project's configured production branch. So we set the limitedlevelups project's production branch to `master` and change the workflow to trigger on master and deploy `--branch=master`. After cutover, master is the single source for the public site, the bot, and previews.

**dev becomes redundant.** Its only job was feeding limitedlevelups.com. Post-cutover, master does that. Retire or repurpose dev (see cleanup).

**Bot link flip is a code change, not an env var.** Bump the `public_site_url` default in `bot/config.py`; Railway redeploys on the master push. No Railway env var needed (an env override stays available as an emergency lever).

## Pre-flight checklist

- [ ] `dev` is launch-ready and contains exactly what should go public (it is what limitedlevelups.com serves today). Confirm `dev` is rebased on / up to date with `master` so the merge is clean.
- [ ] Decide merge strategy for `dev → master`: **squash** vs **merge commit preserving history** (launch-plan convention is to ask). 
- [ ] Decide 301 vs 302 for first ship (recommend 302).
- [ ] Low-traffic window scheduled; `.env.cloudflare` tokens on hand for the CF project-setting change.
- [ ] Confirm the limitedlevelups GitHub Actions secrets still resolve: `CLOUDFLARE_API_TOKEN` (= chordocoach account token) + `CLOUDFLARE_ACCOUNT_ID`.
- [ ] Note the OAuth caveat (see below) if anyone will test login on a preview.

## Cutover steps

### Phase 1 — land everything on master

Do the code edits on `dev` (or a short-lived branch off master), then merge.

1. **Add the redirect guard** to `functions/_middleware.ts` — the hostname check at the top of `onRequest`, before the `context.next()` / asset fetch logic. Use `302` for the first ship.
2. **Flip the bot default** in `bot/config.py`: `public_site_url: str = "https://limitedlevelups.com"`.
3. **Update hardcoded URLs**: `prompts/championship-announcement.md`, `README.md`, and the `CLAUDE.md` line-10 note (`dischord.pages.dev` today → launched on `limitedlevelups.com`). Spec docs are historical; update opportunistically.
4. **Merge `dev → master`** with the chosen strategy. master now carries the new sections + redirect + bot link flip. (Do not push yet if you want to stage the CF setting change first — see Phase 2.)

### Phase 2 — repoint limitedlevelups at master

5. **Change the limitedlevelups production branch** `dev → master` (chordocoach account). API:

```bash
set -a; source .env.cloudflare; set +a
curl -s -X PATCH \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN_CHORDO" \
  -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID_CHORDO/pages/projects/limitedlevelups" \
  --data '{"production_branch":"master"}'
```

(Or Dashboard → chordocoach → Workers & Pages → limitedlevelups → Settings → Build → Production branch.)

6. **Update `.github/workflows/deploy-pages.yml`**: `on.push.branches: [master]` and the deploy command `--branch=master`. Commit on master.

### Phase 3 — push and let it cut over

7. **Push master.** One push fans out to three deploys:
   - GitHub Action → `wrangler pages deploy --branch=master` → limitedlevelups.com production. Content is identical to what dev served, so no visible change there.
   - dischord CF native build → `dischord.pages.dev` now serves the middleware with the redirect guard → production dischord 302s to limitedlevelups.com.
   - Railway → bot redeploys, emits limitedlevelups.com links.

   Concurrent is safe: the redirect target (limitedlevelups.com) is already up and serving equivalent content, so there is no window where dischord redirects to a cold site.

## Verification

- [ ] `curl -sI https://dischord.pages.dev/leaderboard` → `302` (or `301`) with `location: https://limitedlevelups.com/leaderboard`. Repeat for `/`, `/pods`, a deep path with a query string.
- [ ] `https://limitedlevelups.com/` and `/leaderboard`, `/tier-list`, `/episodes`, `/community`, a player page, a set leaderboard — all load, correct content, correct canonical tag (`view-source` → `link[rel=canonical]` points at limitedlevelups.com).
- [ ] `https://limitedlevelups.com/sitemap.xml` → all `<loc>` on limitedlevelups.com.
- [ ] **Preview still works**: push a throwaway feature branch, confirm `https://<branch>.dischord.pages.dev` serves real content and does **not** redirect.
- [ ] **Bot**: trigger `/leaderboard` (or `!refresh`) and confirm the footer link and any pod URL point at limitedlevelups.com. Confirm an old dischord link from Discord history redirects.
- [ ] No redirect loop on `www.limitedlevelups.com` (it 301s to apex via the existing CF redirect rule, then apex serves).

## Rollback

Each layer is independently reversible:
- **Redirect** — revert the `functions/_middleware.ts` guard and push; dischord.pages.dev serves content again. If 301 was already shipped and cached, expect browser-cache stickiness (another reason to ship 302 first).
- **limitedlevelups feed** — set production branch back to `dev` and revert the workflow trigger; redeploy dev.
- **Bot links** — set Railway env `PUBLIC_SITE_URL=https://dischord.pages.dev` (overrides the code default instantly without a code revert), or revert `bot/config.py`.

## Post-cutover cleanup

- [ ] Once stable (24-48h), promote the redirect `302 → 301`.
- [ ] Retire or repurpose `dev` (no longer a deploy target). If keeping it as a staging branch, drop the now-unused `dev` trigger from the workflow.
- [ ] Update remaining `spec/*` references to dischord.pages.dev for accuracy.
- [ ] Submit limitedlevelups.com sitemap in Google Search Console; optionally mark the dischord property as moved.
- [ ] Update the [[reference-cloudflare-two-account-setup]] and [[project-llu-launch-plan]] memories to reflect launched state.

## Caveats

- **OAuth on previews** — Supabase Auth allows redirect URLs for `localhost`, exact `dischord.pages.dev`, and `limitedlevelups.com` only. Login on a `<branch>.dischord.pages.dev` preview will fail the redirect; anonymous browsing is unaffected. Add a preview wildcard to the Supabase allowlist only if preview-login testing is needed. See [[project-discord-oauth]].
- **Preview indexing** — `robots.txt` allows all and previews self-canonicalize to their own origin, so feature-branch previews could be crawled. Minor; optionally noindex preview hostnames if it becomes a problem.
- **dischord project still builds the full site** just to serve a redirect on production — intentional, because the git connection is what gives free feature-branch previews. Keep the project connected.
