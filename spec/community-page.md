# Community page spec

The redesign target for `/community`. This page is the last section to polish before the `limitedlevelups.com` launch. The current live `/community` is the **baseline to beat** — a rebuild only ships if it is clearly better: more compact, better framed, less redundant. Several earlier attempts (`CommunityA/B/C`) failed to beat it; this spec exists so the next attempt is decisive.

## Status — shipped

The rebuild is **built, shipped, and committed**. The `CommunityA/B/C` experiments are deleted. The as-built design is described under [Layout](#layout--as-built) below; apply further change-notes against the files in the map.

**File map:**
- `frontend/src/pages/CommunityPage.tsx` — the page composition (route `/community` in `App.tsx`). Has local `MemberCount` and `highlightBrand` helpers.
- `frontend/src/data/community.ts` — copy + data + hooks: `COMMUNITY_DISCORD_HEADING`, `COMMUNITY_DISCORD_PITCH` (derived from `DISCORD_BLURB`), `COMMUNITY_INTRO_PARAGRAPHS`, `COMMUNITY_HIGHLIGHTS`, `COMMUNITY_SHOW_PARAGRAPHS`, `COMMUNITY_SUPPORT_NOTE`, `COMMUNITY_SUPPORT_REWARDS`, `COMMUNITY_SHOW_TOPICS`, `COMMUNITY_EVENTS` (each a `CommunityLink` with `title`/`steps`/`to`/`cta`/`Icon`), `useCommunityStats()` (Discord member/online), `categoryHref()`.
- `frontend/src/components/CommunityBits.tsx` — atoms: `CommunityHeading`, `SectionPanel` (+ internal `PanelShell`/`PanelHeader`), `HostBlock`, `HostMug`, `EventCard` (bulleted-steps card with a floated CTA on the last step), `SupportCard` (+ `SupportRewards`), `ShowTopics`, `CommunityLinks`. Holds the lucide `CATEGORY_ICON` map and the `renderStep` markdown-ish tokenizer (`/slash` code spans + `[label](href)` links).
- `frontend/src/components/CategoryTag.tsx` — `CATEGORY_COLOR` (text colors) + `CATEGORY_STYLE` (pill bg).
- `frontend/src/data/site.ts` — `SITE_BLURB` / `SITE_BLURB_PARAGRAPHS`, `DISCORD_BLURB` (the canonical copy), `HOSTS` (with optional `Host.photo`), `SITE_LINKS`.

**Run & verify:** dev server is `cd frontend && npm run dev` on `:5173`. Typecheck with `cd frontend && npx tsc -b 2>&1 | grep -v "LeaderboardTable.tsx"` — must be empty. `LeaderboardTable.tsx` has a pre-existing `if (true) return <LoadingRows/>` debug hack (NOT ours) that errors tsc and blocks `npm run build`; ignore it or have the owner revert it. Vite's file watcher has been **flaky** — it silently serves stale module transforms after edits (caused a blank page once). If a change doesn't show or the page breaks unexpectedly, `touch` the edited file or restart `vite`; confirm freshness with `curl -s localhost:5173/src/<path> | grep <symbol>`.

**Open items:**
- **Host photos** — Alex (`Chord_O_Calls`) and Marc (`NEO_MTG`) currently fall back to `xAvatar(handle)` (their X profile image) via `Host.photo`. Drop dedicated squares in `frontend/public/` and point `Host.photo` at them when available. Bios are written and live; Marc's is "former Canadian National Champion / Limited consultant for Cosmos Heavy Play".
- **Orphaned components** confirmed unreferenced after the rebuild: `components/DiscordBand.tsx`, `components/HostCard.tsx` (the old `PlatformCard.tsx` is already deleted). Safe to prune — nothing imports either.

## Positioning

This is the **"About Us" page.** Home is the live dashboard; Community explains who Limited Level-Ups is and converts a visitor into a Discord member. It must read as compact and information-dense — the most relevant information on the first screen, no long scroll, no oversized hero. If it feels like a slower, emptier version of Home, it has failed.

## Goals, in priority order

1. **Join the Discord, knowing what to expect.** The primary conversion. Lead with the invite.
2. **The two activities featured on the site: pod drafts and the leaderboard.** Framed as a place to *share your own drafts, stats, and trophies under your name* — never as competition, ranking, or "#1". Personal-accomplishment framing, not leaderboard-grind framing.
3. **A short section on the hosts.**
4. **Episode cadence and the kinds of content made.** What the show is, how often, what types — not a feed of episodes.

## Hard don'ts (each of these was tried and rejected)

- **Not a live dashboard. Do not duplicate Home.** No "latest episode" link, no current pod winner, no current #1 player. The one allowed live element is the **Discord member / online count** — it is a community-size signal that sells the join, not a feed.
- **No cringe eyebrows or invented kickers.** Killed: "SINCE 2020 · LIMITED MAGIC", "TOGETHER", "OFF DISCORD", "THE BRAND", "WHO RUNS IT".
- **Do not repeat "Limited Level-Ups" in the H1.** The page header already brands the page (logo + "COMMUNITY"). An H1 of "The Limited Level-Ups Discord" double-states it.
- **No syrupy or marketing copy. No invented taglines.** Killed: "where the community lives", "footprint across every platform", "chill coffee shop", "both kept on the site so your drafts have a home and a name", "Level up your Limited game" (invented tagline). Voice is dry, concrete, understated — senior engineer, not hype.
- **Do not waste horizontal space.** A tall, narrow, left-aligned hero column that leaves the entire right half empty is the single most-rejected layout. Use the width.
- **No weak umbrella section titles.** "What the community does" is bad. Name things concretely or drop the umbrella and let the cards stand.

## Canonical copy — use verbatim, single source in `data/site.ts`

**Website blurb** (`SITE_BLURB`, brand identity — YouTube + podcast + Discord):

> Limited Level-Ups is a YouTube channel, podcast, and Discord community for Magic: The Gathering players of all skill levels who want to improve at Limited.
>
> Whether you're looking to get your first trophy, sharpen your fundamentals, or compete at the highest level, Limited Level-Ups is here to help you level up your game.

**Discord blurb** (`DISCORD_BLURB`, the server invite):

> The Limited Level-Ups Discord is a home for Limited players of all skill levels. Whether you're looking to improve your drafting, discuss formats, share your latest trophies, or just chat with other Limited enthusiasts, you'll find a welcoming group of players here.

Both are Alex-approved. Capitalization normalized to sentence case + correct "YouTube" spelling. When a heading already says "Discord", drop the self-identifying lead from the blurb so it doesn't repeat.

## Visual system — extend, don't reinvent

Dark surfaces (`bg`, `surface`), green accent, `font-display` + `mono` pairing, `ChamferCta`, `SectionLabel`, hairline dividers, square corners (the app is mostly border-radius-free). `Container` caps at 1760px.

Elements explicitly liked and worth keeping:
- The **gradient band** (the `DiscordBand` look) for the invite.
- **Bordered boxes / cards.**
- The **Episodes LIBRARY category treatment** — per-category lucide icon in its category color (`CATEGORY_COLOR` in `CategoryTag.tsx`), uppercase label, episode count, green left-bar + green-text on hover. Reuse this for the show's content types.

## Inspiration — gather before the next polish pass

**TODO (not yet done):** collect 4–6 real community / "about" pages worth stealing from, paste the links here with a one-line note on what to take from each. The point is to anchor the next pass in proven layouts instead of guessing. Look for pages that solve the same job this one does: a single screen that says "here's the community, here's what you do here, join" — dark, dense, gaming/creator-adjacent, with a strong primary CTA.

What to look for specifically:
- How they pack identity + "what you get" + a join CTA above the fold without a giant empty hero.
- How they present recurring activities/events compactly (our pods + leaderboard).
- How they handle a small "the people behind it" section without it feeling like a corporate team page.
- Dark-theme density done well — information-rich but not cluttered.

Where to mine (filter for community / about / dark):
- Galleries: [Awwwards](https://www.awwwards.com), [Land-book](https://land-book.com), [Godly](https://godly.website), [Lapa Ninja](https://www.lapa.ninja), [Refero](https://refero.design), [Mobbin](https://mobbin.com) (app patterns), Dribbble / Behance ("community page dark").
- Dark-mode roundups for execution detail: [Lovable dark-mode examples](https://lovable.dev/guides/dark-mode-website-examples-guide), [Framerbite dark-mode inspiration](https://framerbite.com/blog/dark-mode-website-design-inspiration).
- Peer communities' own sites: Discord-driven gaming/creator communities, streamer/Patreon community hubs, and MTG-adjacent sites — for how they frame "join + what to expect + events + who runs it."

Seed examples:

Patreon creator pages (researched 2026-06; live-fetched unless noted) — the canonical anatomy is identity/about + CTA on the left, value/content weighted right, with the join button as the biggest interactive element and the member count glued under it as social proof, not a bare stat. None use a giant empty hero. Validates our two-column top band; the lesson is hierarchy within it, not restructure.
- https://www.patreon.com/philosophytube — CTA copy fuses action + social proof ("join a community of N members"). Make JOIN carry the live count, don't float it as a neutral metric.
- https://www.patreon.com/thecuttingroomfloor — one-sentence creator bio → value line → CTA, in that order, no filler. Steal the left-column copy ordering.
- https://www.patreon.com/loadingreadyrun — counts shown as a quiet supporting row under the tagline; platform links sit inline with creator identity rather than a separate trailing section. Basis for folding "Find us elsewhere" into the hosts row.
- https://support.patreon.com/hc/en-us/articles/8293386737677 — official: lead the About with who you are + what you make, then what fans get in return.

## Layout — as built

**Hero band** (single gradient `section`, `#14181f → #0a0c10`, full-bleed with bottom hairline). Two columns at `lg`, stacked + centered below:
- Left: the invite — H1 `COMMUNITY_DISCORD_HEADING` ("A home for Limited players", *not* the brand name), the `COMMUNITY_INTRO_PARAGRAPHS` body with "Limited Level-Ups" / "level up your game" emphasis via `highlightBrand`.
- Right: the **JOIN THE DISCHORD** `ChamferCta` (Discord glyph, `size="lg"`, `grow`) with the live member/online count glued beneath it (`MemberCount`), then the `COMMUNITY_HIGHLIGHTS` list (four icon + line items). At `xl` the CTA block and highlights split apart via `xl:contents`.

**Body grid** (`Container`, `grid lg:grid-cols-2 gap-6`), four panels:
- **Community leaderboard** — `EventCard`, three `steps` ("Type /join…", "Share your trophies…", "See the drafts and decks…"), CTA "View the leaderboard" → `/leaderboard`. Accomplishment-framed.
- **Weekly pod drafts** — `EventCard`, three `steps` (sign up in the linked Discord channel, draft on Draftmancer + play on MTGA, seats/logs/replays saved), CTA "Check past & upcoming events" → `/pods`.
- **The show** — `SectionPanel`, the `COMMUNITY_SHOW_PARAGRAPHS` cadence/content copy, the `ShowTopics` chip row (`COMMUNITY_SHOW_TOPICS`: set reviews, format updates, evergreen, drafts — each links to `/episodes/<category>`), then a hairline-divided **SUPPORT** subsection (`CommunityHeading` + Patreon glyph) holding `SupportCard` (the support note, **BECOME A PATRON** cta, and the `SupportRewards` chips). `order-first lg:order-none` so it leads on mobile.
- **The hosts** — `SectionPanel`, one `HostBlock` per `HOSTS` entry (avatar, name + X handle, role, bio), hairline-divided.

**Elsewhere** is **not a page section** — the YouTube / Podcast / Spotify / Apple / RSS / Patreon links live in the shared `SiteFooter`, so the page doesn't duplicate them. (`CommunityLinks` remains in `CommunityBits` but is not mounted on this page.)

## Section titles

- Hero H1: `COMMUNITY_DISCORD_HEADING` ("A home for Limited players").
- Activities: **no umbrella title** (decided) — the two `EventCard`s stand alone, self-titled "Community leaderboard" and "Weekly pod drafts".
- "The show" (with a nested "SUPPORT" subsection).
- "The hosts".
- No "Find us elsewhere" on the page (folded into the footer).

## Data

- `useDiscordStats` (via `useCommunityStats`) → member / online count, the only live element.
- No per-category episode counts — `ShowTopics` links to category pages by label, without counts.
- No `useLeaderboard` / `usePodEvents` — no live winners or ranks.
- Category links → `/episodes/<slug>` via `categoryHref` / `categorySlug`.

## Reuse

`ChamferCta`, `SectionLabel`, `Container`, `AAvatar`, `CategoryTag` (`CATEGORY_COLOR` / `CATEGORY_STYLE`), the lucide category icon map. Shared community data/copy stays in `data/community.ts`; presentational atoms in `components/CommunityBits.tsx`.

## Open items

- **Host photos** — Alex (`Chord_O_Calls`) and Marc (`NEO_MTG`) currently render their X avatars (`xAvatar`); swap in dedicated `frontend/public/` squares when available.
- **Activities section title** — decided: no umbrella, the two cards stand alone.
- The unverified stats (subscriber/patron counts) are gone for good; only the live Discord count remains.

## Testing

Primary desktop target **1280px wide** — if it holds there it holds up to the 1760px cap. Spot-check 1920 and 2560 (cap should center with even gutters). The layout's only shape change is at `lg` (1024px), below which it stacks to one column.
