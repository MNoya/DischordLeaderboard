# Discord OAuth Spec — Identity Layer

## Context

The frontend at `dischord.pages.dev` is fully anonymous today — Supabase anon key, read-only `public_*` views, no user identity. This spec adds Discord OAuth so the site knows who the visitor is (Discord ID, username, avatar). This unlocks future features (voting, personalized views, self-service settings) but the initial PR is just the auth plumbing — login, logout, session, and the visual indicator in the header.

No bot changes. No RLS changes. No new tables or migrations. No features that consume auth. Just the identity layer.

---

## Identity Model

Two-tier, no new tables:

- **`auth.users`** (Supabase-managed) — created automatically when anyone logs in with Discord. Stores Discord ID, username, avatar. Universal identity for all website visitors. Future contest/voting tables FK here.
- **`players`** (bot-managed) — leaderboard participants only, created by the bot's `/join` flow. Has `discord_id` column.
- **Linking:** When a logged-in user is also a leaderboard player, we match them at read time by joining `auth.users.raw_user_meta_data->provider_id` to `players.discord_id`. No migration, no explicit "link account" step.

Someone can log in to vote in a contest without ever joining the leaderboard. Leaderboard players who log in are automatically recognized.

---

## Auth Flow

**Login:**
1. User clicks "LOG IN" in the header
2. `supabase.auth.signInWithOAuth({ provider: 'discord', options: { redirectTo: window.location.href } })`
3. Browser -> Supabase auth endpoint -> Discord consent screen (scope: `identify` only)
4. Discord -> Supabase callback (`https://yrecdosksgigpceholjl.supabase.co/auth/v1/callback`) -> Supabase exchanges code, mints session -> redirects browser back to `redirectTo` URL with PKCE tokens as hash fragments
5. Supabase JS client auto-detects fragments on page load, stores session in `localStorage`, fires `onAuthStateChange(SIGNED_IN)`
6. `AuthProvider` picks up the event, React re-renders

Using `window.location.href` as `redirectTo` means the user lands back on the exact page they were viewing.

**Logout:**
1. User clicks "Log out" from user menu
2. `supabase.auth.signOut()` -> clears `localStorage` -> fires `onAuthStateChange(SIGNED_OUT)`
3. Header reverts to login button

**Token refresh:** Handled automatically by Supabase JS client. No custom code.

---

## Session Management

Flip `persistSession` from `false` to `true` in `frontend/src/data/supabase.ts`. Session survives page reloads via `localStorage` under key `sb-yrecdosksgigpceholjl-auth-token`. Mock mode (`supabase === null`) is unaffected.

---

## React Integration

**New: `frontend/src/auth/AuthContext.tsx`**

```
AuthUser {
  id: string           // Supabase auth user UUID
  discordId: string    // user_metadata.provider_id
  username: string     // user_metadata.full_name or custom_claims.global_name
  avatarUrl: string    // user_metadata.avatar_url (Discord CDN)
}

AuthContextValue {
  user: AuthUser | null
  loading: boolean     // true during initial session hydration
  signIn: () => void
  signOut: () => void
}
```

- On mount: `supabase.auth.getSession()` to hydrate from `localStorage`, then set `loading = false`
- Subscribes to `onAuthStateChange` and maps `session.user.user_metadata` -> `AuthUser`
- When `supabase` is null (mock mode): always `{ user: null, loading: false, signIn: noop, signOut: noop }`

**New: `frontend/src/auth/useAuth.ts`** — `useContext(AuthContext)` wrapper.

**Provider placement in `frontend/src/main.tsx`:**
```
<QueryClientProvider>
  <BrowserRouter>
    <AuthProvider>
      <App />
    </AuthProvider>
  </BrowserRouter>
</QueryClientProvider>
```

---

## UI — AppHeader

**Desktop (inline nav visible):**
- Right side of header, after the inline nav
- Logged out: ghost-style button "LOG IN" matching nav item aesthetic (`font-display`, `tracking-[0.14em]`, border)
- Logged in: Discord avatar (24-32px, `rounded-full`) + display name (truncated). Click opens minimal dropdown with "Log out"

**Mobile (collapsed nav):**
- Logged out: "LOG IN" as last item in the slide-in menu, styled like nav links
- Logged in: avatar + name at top of slide-in menu, "Log out" at bottom

---

## Cloudflare Pages

**No middleware changes needed.** The PKCE flow redirects back to the user's original URL with hash fragments — the SPA fallback already serves `index.html` for that path, and Supabase JS parses the fragments client-side.

---

## One-Time Configuration (outside the PR)

**Discord Developer Portal:**
1. Create app (or reuse existing DisChord Bot app — see open questions)
2. Add OAuth2 redirect URI: `https://yrecdosksgigpceholjl.supabase.co/auth/v1/callback`
3. Scope: `identify` only (no `email`)

**Supabase Dashboard:**
1. Authentication -> Providers -> Discord: enable, paste Client ID + Secret
2. URL Configuration: Site URL = `https://dischord.pages.dev`, add `http://localhost:5173` to allowed redirects

No new frontend env vars. Discord credentials live in Supabase's server-side config.

---

## File Changes

| File | Change |
|---|---|
| `frontend/src/data/supabase.ts` | `persistSession: false` -> `true` |
| `frontend/src/auth/AuthContext.tsx` | **New.** AuthProvider + context |
| `frontend/src/auth/useAuth.ts` | **New.** Convenience hook |
| `frontend/src/main.tsx` | Wrap `<App>` in `<AuthProvider>` |
| `frontend/src/components/AppHeader.tsx` | Login button / avatar+name+logout in both desktop and mobile layouts |

No changes to: `_middleware.ts`, `App.tsx`, `package.json`, data layer, types.

---

## NOT in Scope

- No RLS policy changes (comes with features that need gated data)
- No bot changes
- No explicit "link account" flow (player recognition is automatic via `discord_id` match)
- No protected routes or auth guards (all pages stay public)
- No feature code that consumes auth (no voting, no profile editing)
- No mock-mode auth

---

## Verification

1. `npm run dev` -> site loads, no auth errors in console
2. Click "LOG IN" -> redirects to Discord consent -> redirects back to same page
3. Header shows Discord avatar + name
4. Refresh page -> session persists (still logged in)
5. Click "Log out" -> header reverts to login button, `localStorage` cleared
6. Anonymous browsing still works identically (no regressions on leaderboard, pods, about pages)
7. `npm run build` succeeds

---

## Open Questions for Maintainer

1. **Discord app:** New OAuth app, or reuse the existing DisChord Bot app (`1466076574372724819`)? Reusing is simpler but couples bot + website config.
2. **Login button style:** Ghost border (matching nav), green accent, or Discord-branded (#5865F2)?
3. **Display name:** Show `global_name` (friendly display name) or `username` (unique handle)?
