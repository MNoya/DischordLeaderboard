# Pod deck modal — handoff (UI polish + Draft Log MVP)

Fresh-session handoff. Two focuses: **(A) UI tweaks** on the pod deck modal, and **(B) an MVP of the Draft Log** — a pick-by-pick draft review as a third tab in that modal.

## Where things live

- **Modal:** `frontend/src/components/pod/DeckScreenshotModal.tsx` — the deck preview. Tabs, seat prev/next, mobile layout, sideboard, breakdown CTA all live here.
- **Artifact derivations:** `frontend/src/data/draft-artifact.ts` — `resolveDeck(artifact, seatIndex)` today; the Draft Log adds a `resolvePicks` sibling here.
- **Fetch/hook:** `fetchPodDraftArtifact` (`frontend/src/data/realApi.ts`) + `usePodDraftArtifact` (`frontend/src/data/hooks.ts`), reading the `public_pod_draft_log` view.
- **Types:** `PodDraftArtifact`, `Mainboard`, `MainboardCard` in `frontend/src/types/leaderboard.ts`.
- **Pages that open the modal:** `frontend/src/pages/PodDraftsPage.tsx` (the `/pods` hub, `EventStandings`) and `frontend/src/pages/PodPage.tsx` (`/pods/<slug>` breakdown). Both compute `resolveDeck(artifact, seatIndex)` in a memo and pass it as `mainboard`, and pass `onPrev`/`onNext` that cycle the seat full-circle.
- **Set switcher:** `frontend/src/components/SetSwitcher.tsx` (release-date sort lives in `partitionSets`).
- **Python reference for the Draft Log:** `simulate()` in `bot/scripts/draftmancer_log.py`.

## Current deck-modal UI (what's already there)

- **Tabs:** `IMAGE` (the posted deck screenshot) and `CARD POOL` (the reconstructed deck: maindeck as mana-value piles + a sideboard row). `tab` is a **sticky preference**; `effectiveTab` falls back per seat to whatever that seat actually has.
- **Sideboard:** a continuous horizontal row in its own box below the caption, on the CARD POOL tab, only when `mainboard.sideboard` is non-empty. **Historical events have no sideboard** (`mainboard_card_ids` only ever captured the maindeck, so the backfill set `side: []`); it populates for new drafts and in mock mode (`mock-sos-mock-1`, seat 0).
- **Seat prev/next:**
  - **Desktop (≥ lg):** chevrons flank the modal *outside* it; `PREV`/`NEXT` labels appear at `≥1600px`. ← / → keys also navigate; the pod-page arrow nav is suppressed while the modal is open.
  - **Mobile (< lg):** flanking chevrons + header tab bar are hidden; instead a **detached rounded floating panel sits below the modal** (Trello-style) holding `‹ IMAGE CARD POOL [breakdown] ›`.
- **Breakdown CTA:** desktop shows the footer bar (caption + "Seats, logs & replays" + `VIEW BREAKDOWN`); mobile shows **caption-only** footer and a green round-table **breakdown pill** in the floating panel. Only present on the `/pods` hub modal (the breakdown page itself omits it).
- **Caption:** unified styling across both modals (15px italic, 2.25rem left inset).

## Focus A — UI tweaks backlog

- **Mobile modal width (flagged).** Removing the flanking chevrons freed width and the modal briefly went edge-to-edge; it's currently inset via overlay `px-4 md:px-6` with the modal `w-full lg:w-auto`. Revisit the exact inset/margins — the user wants it clearly *not* full-bleed. This is the open item that prompted this handoff.
- Verify the mobile floating panel + breakdown pill on a real phone viewport (iPhone 14 Pro in devtools); confirm tap targets and the gap above the panel feel right.
- Confirm desktop is untouched by the mobile work (flanking chevrons, header tabs, footer bar).
- The `VIEW BREAKDOWN` placement is intentional: hub modal has it, breakdown page doesn't. Leave unless revisited.

## Focus B — Draft Log MVP (the third tab)

**Goal:** add a `DRAFT LOG` tab beside `IMAGE` / `CARD POOL` that walks one seat's draft pick by pick — for each pick, show the pack as the player saw it with the taken card highlighted, and step through P1P1 → P3P14. Model the layout on the [Draftsim recap](https://draftsim.com/recap/?id=57ol2yMMR) (single-pick stepper with pack context) and [MagicProTools](https://magicprotools.com/). Works for **all** events: it needs only `packs` + `picks`, which every artifact has (unlike `CARD POOL`, empty for the 12 historical events).

**The one real piece of logic — port `simulate()` to TS** in `draft-artifact.ts`, extended to expose the pack *as seen* at each pick (the Python version only returns the taken card). The Python algorithm:

```python
PASS_DIRS = (+1, -1, +1)  # pack 1 passes one way, pack 2 the other, pack 3 like pack 1
for pack_num in range(3):
    booster_at = [list(packs[seat + pack_num * n_seats]) for seat in range(n_seats)]
    direction = PASS_DIRS[pack_num]
    for pick_num in range(len(booster_at[0])):
        for seat in range(n_seats):
            pick_idx = picks[seat][pack_num][pick_num]
            taken = booster_at[seat].pop(pick_idx)   # booster_at[seat] *before* the pop is the pack as seen
        booster_at = [booster_at[(seat - direction) % n_seats] for seat in range(n_seats)]
```

Proposed surface (mirrors `resolveDeck`, so the modal stays dumb and is fed a prop):

```ts
resolvePicks(artifact, seatIndex): { packNum: number; pickNumber: number; seen: ResolvedCard[]; takenIndex: number }[] | null
```

Verify the port against Python by spot-checking `LLU-SOS-Championship-A`: the taken cards must equal `picks`. (`python -m bot.scripts.draftmancer_log verify <rawlog>` proves the Python is lossless.)

**Artifact shape** (`PodDraftArtifact`): `seats: string[]` (index === participant `seatIndex`); `cards: { n, cn, s, r, c, cmc, type }[]` (image via `s`+`cn`, Scryfall — `scryfallImageUrl` already in the modal file); `packs: number[][]` (booster opened by `seat` at start of `packNum` = `packs[seat + packNum*nSeats]`); `picks: number[][][]` (`picks[seat][packNum][pickOrder]` = index within the pack-as-seen of the taken card).

**Modal wiring:**
- Add `"draftlog"` to the `DeckTab` type; render the tab in **both** the desktop header tab bar and the mobile floating panel pills. The DRAFT LOG tab is available whenever the artifact has packs (independent of screenshot/decklist) — today the tab bar only shows when `hasScreenshot && hasDecklist`, so rework that gate.
- Feed it via a `resolvePicks(artifact, seatIndex)` memo + a new prop on `DeckLike`, mirroring how `mainboard` is passed from `PodDraftsPage`/`PodPage`. Both already fetch the artifact and recompute per `deckTarget`, so seat prev/next swaps the Draft Log seat for free.

**UI (MVP):** pack grid of `seen` cards, the `takenIndex` card highlighted (green border/glow); a `P{packNum+1}P{pickNumber+1}` counter; prev/next **pick** controls that roll into the next pack at a pack's end.

**Decisions to make:**
1. **Pick nav vs seat nav.** ← / → and the chevrons currently switch **seats**. In the Draft Log tab the natural mapping is ← / → = prev/next **pick**. Pick one: remap arrows to picks in this tab (seats via on-screen buttons), or keep arrows on seats and give picks their own prominent controls.
2. **Mock data:** add `packs`/`picks` to the mock fixture (`frontend/src/data/fixtures/pod-events.ts`, `mock-sos-mock-1`) to exercise the Draft Log without a backend.

**Privacy:** pods are always public; full pick history is fine to expose. No gating.

## Repo state (2026-06-14)

- Branch **`pod-draft-artifact`** off `master`. Commits: `cc31f82` (backend: the artifact + `public_pod_draft_log`, mainboard columns retired) and `1404e57` (frontend: deck view from the artifact — CARD POOL + sideboard, seat prev/next, set sort, profile tooltip). **Nothing pushed.**
- **Uncommitted working tree:** `frontend/src/components/pod/DeckScreenshotModal.tsx` (the mobile floating-panel + breakdown-pill + margin tweaks) and this doc. Everything else is committed.
- **Local DB:** pg17 container `dischord-pg17` on `:5433`, restored from prod with `draft_log` backfilled (12 events with decks, 6 picks-only; all 18 have `packs`/`picks`). Safe-point dump: `~/dischord-prod-backup-2026-06-14.dump`. Old pg16 `dischord-pg` stopped but intact.
- **Run it:** `DATABASE_URL=postgresql://postgres:devpw@localhost:5433/dischord python -m bot.scripts.local_supabase_proxy` (proxy on `:3001`, whitelists `public_pod_draft_log`), then `cd frontend && npm run dev` with `VITE_DATA_MODE=local` in `frontend/.env.local` (gitignored). Was last serving on `:5174`. `VITE_DATA_MODE=mock` uses fixtures (no backend) — good for the mock-data Draft Log work.
- The backend artifact is final; the Draft Log is purely frontend. `simulate()` is the only non-trivial logic and it's already written/verified in Python.
