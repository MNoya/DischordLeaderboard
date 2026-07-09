# P0P1 Final Standings — Champion Spotlight

Design mockups (five explored treatments, A chosen, plus mobile variants): https://claude.ai/code/artifact/fa81f190-30b5-4142-b4bb-d6148bea5e32

## Problem Statement

On the P0P1 FinalResults overview, the "TOP STANDINGS" section renders the top three ballots as ordinary list rows — identical to every other row on the board. Winning the community pick-rating contest for a whole set window earns no visual recognition: the champion's row looks the same as #14's. The reveal moment the final-results phase is built around falls flat.

## Solution

Replace the top of the overview's standings peek with a **champion spotlight**: the winner gets a large gold-framed card showing their name, medal, glowing final score, and their actual winning ballot as a strip of card art; 2nd and 3rd place get silver- and bronze-accented rows; everyone else stays in the familiar list. The treatment applies to the overview tab only — the FULL RESULTS tab keeps its uniform expandable list.

## User Stories

1. As the P0P1 champion, I want my name, avatar, and score displayed dramatically at the top of the results, so that winning the contest feels like an achievement worth chasing next set.
2. As the champion, I want my eight winning picks shown as card art on my spotlight card, so that everyone can see *what* I picked, not just that I scored highest.
3. As a 2nd- or 3rd-place finisher, I want my row visibly medaled (silver/bronze) and distinct from the field, so that a podium finish still reads as special.
4. As any participant, I want ranks 4+ to render exactly as before, so that the standings below the podium stay scannable and familiar.
5. As a participant outside the top 3, I want my own row still pinned beneath the peek with the "YOU" treatment, so that I can find my result without opening the full list.
6. As a participant who placed 2nd or 3rd, I want my medal row to also carry the self-highlight, so that I can tell it's me at a glance.
7. As any viewer, I want to hover or tap a card in the winning-ballot strip and see the full card, so that I can inspect the picks without leaving the overview.
8. As any viewer, I want the 2nd/3rd rows to stay expandable into their pick grids, so that podium ballots are as inspectable as everyone else's.
9. As a mobile visitor, I want the champion card to reflow (score under the name, picks as a 4×2 art grid) so that card names stay legible at phone width.
10. As any viewer, I want the "SEE ALL N STANDINGS →" affordance and fade to remain, so that the path to the full list is unchanged.
11. As a viewer of the FULL RESULTS tab, I want the standings there unchanged, so that dense comparison scanning isn't disrupted by ceremony styling.
12. As a returning site user, I want the spotlight built from the site's existing visual language (chamfers, Bebas display type, mono scores, gold trophy color), so that it feels native to LLU rather than bolted on.
13. As the champion whose ballot ties another ballot's score, I want rank order to stay exactly what the standings algorithm produced, so that the spotlight never disagrees with the list.

## Implementation Decisions

- **Chosen treatment**: mockup option A ("Champion Spotlight"). Options B (podium), C (medal rows), D (broadcast overlay), E (trophy plinth) were explored and rejected; D was the runner-up but degrades worse at phone width.
- **Scope**: overview tab's TOP STANDINGS section only. Peek behavior (top 3 + pinned self + fade + see-all) is preserved; only the *rendering* of ranks 1–3 changes.
- **Champion card** (rank 1): chamfered card using the shared chamfer clip-path, gold **gradient** border with an ambient glow bloom (deliberately punchier than the existing YourResultCard, which was judged too bland), oversized ghost Bebas "1" numeral behind the content, gold-ringed avatar, "🥇 CHAMPION" display eyebrow, player name, "Top X% of N ballots" subline from the existing percentile, and a large gold mono score with text-shadow bloom labeled "FINAL SCORE".
- **Winning ballot strip**: the champion's eight picks (one per P0P1 slot) as art-crop tiles under a "THE WINNING BALLOT" label. **Tiles are rectangular — no skew/chamfer — matching the existing pick-grid card tiles** (explicit user decision; the mockup's slanted tiles are superseded). Each tile: card art crop, slot-accent top strip (the existing per-slot accent colors), card name caption, and the existing hover/tap full-card tooltip pattern already used by the contribution bar.
- **2nd/3rd rows**: variants of the existing standings row — Bebas "2ND"/"3RD" in place of the mono rank, medal-colored inset left edge, faint medal tint gradient, medal-ringed avatar, medal-colored score. Still expandable into the ballot's pick grid; still compose with the self-highlight.
- **Medal colors**: the existing PODIUM constants (gold/silver/bronze) already defined in the final-results module — no new palette.
- **Data seam**: everything renders from the existing ranked-ballot output plus the card and rating lookups the standings rows already receive. No new data fetching, no scoring changes, no fixture changes, no backend involvement.
- **Mobile** (below the `lg` breakpoint, matching how the page already adapts): score moves below the name as its own left-aligned line keeping the glow; ballot strip reflows from one 8-across row to a 4×2 grid; ghost numeral scales down; medal and trailing rows tighten padding as the existing rows already do.
- **Self-interaction**: if the viewer *is* the champion, YourResultCard continues to render above as today — the spotlight is not a replacement for it; no deduplication.

## Testing Decisions

- The frontend has no test runner (no test script) and the repo convention is "tests target logic, not framework behavior." The new components are purely presentational with zero logic beneath the existing ballot-ranking seam, so **no new automated tests**.
- Verification is visual: run the dev server in mock data mode with the final-results phase active, check the overview at desktop and ~375px widths against the approved mockup, confirm FULL RESULTS is untouched, and confirm `npm run build` (which runs the TypeScript check) passes.
- Good-test yardstick for any future logic added here: assert on rendered ranks/scores from ballot inputs, never on class names or styling.

## Out of Scope

- FULL RESULTS and BREAKDOWN tabs — unchanged.
- The other four mockup treatments (B/C/D/E).
- Punching up YourResultCard itself (flagged as bland; a natural follow-up using this same visual vocabulary, but not this change).
- The midway-phase reveal, bot behavior, scoring, fixtures, and anything backend.
- Frontend test infrastructure.

## Further Notes

- The mockup artifact embeds the real Bebas Neue woff2 and the app's exact color tokens; its gradient blocks stand in for card art, which the implementation replaces with real art crops.
- The mockup's sample data (winner "oophies", 478.9, the per-slot best picks) is fixture-derived and realistic, so side-by-side comparison against the mock-mode app is meaningful.
