# Pod Format Preference + Format Poll

**Status: DEFERRED — design only, not started.** This spec captures the idea and the open questions so a future session can refine it into a build plan. Nothing here is committed to yet. A Sesh poll screenshot will be provided to anchor the UI style (see "Sesh poll reference" below) — do not lock the visual design until it lands.

## Motivation

Format decisions currently happen too late and too quietly. The format for a pod is decided (or defaulted) somewhere upstream, but by the time players are in the thread nobody is aware they can influence it, and nobody takes the initiative to change it. We want the format to be a visible, low-friction group decision made before the lobby opens.

This is the **format axis** (what you draft: latest set / flashback set / cube / a specific one). It is distinct from the **pairing axis** (bracket vs Team Draft), which is handled separately by the T-60 Team Draft offer. The two decisions can share the pre-lobby surface but are different features.

## The two components

1. **Player format preference (at signup).** When a player RSVPs, they can set a format preference from a small menu. First-cut options: Latest set, Flashback set, Cube. This is the quiet, always-on signal of what each player wants.

2. **Format poll (in the thread).** A poll surface inside the pod thread with the same top-level options plus specific choices, where players can also add their own option. This is the explicit "let's decide this pod's format" moment.

## Core design principle: same data at two moments

The preference and the poll are the same data captured at two points in time. The signup preference is "what I'd want"; the poll is "let's decide." The poll should **open already seeded** with the aggregated signup preferences, so it is never a cold start — if four people picked Flashback at signup, the poll opens with Flashback already leading. This seeding is the spine of the feature and should drive the data model.

## Sesh poll reference

The poll UI is inspired by Sesh's poll style. A screenshot will be provided; mirror its layout and interaction feel (option rows, vote counts, add-your-own affordance) adapted to our surfaces. Hold visual decisions until the screenshot is in hand.

## Open questions to resolve next session

1. **Preference scope.** Is a player's format preference a persistent default (set once, reused every pod) or a per-signup choice (fresh each event), or a persistent default that pre-fills the per-event pick? This decides whether the preference lives on the `Player` model or on the signup/signal row.

2. **Poll resolution.** Does the winning option auto-apply as the pod's format (the way the Team Draft vote auto-locks `pairing_mode`), or is it advisory and a human sets the format from it? Auto-apply best serves the "nobody takes initiative" pain but needs guardrails for ties and late flips. If auto-apply, define the tie-break and the cutoff time after which the format freezes.

3. **Category to concrete.** "Latest / Flashback / Cube" are categories, but a draft needs one concrete format (a specific set or a specific cube). How does "Flashback" resolve to a concrete set? Two-step (pick category, then which one) or a flat list of specific options grouped under headers (e.g. the current set, named flashback sets, Peasant Cube)? This shapes the whole menu.

4. **Native vs custom poll.** "Players can add their own options" rules out Discord's native poll (options can't be added after creation and it can't drive our format setting). Confirm the poll is a custom button/select surface, same family as the Team Draft vote card.

5. **Timing and placement.** When does the poll appear — at thread creation, at a fixed lead time (e.g. T-60 alongside the roster reminder), or on demand? Where does the signup preference menu live — on the RSVP card, in the thread registration embed, or both?

6. **Who can add options, and how are write-ins constrained.** Any player, or organizer only? Free text or picked from a known set/cube registry? A free-text write-in that does not map to a real Draftmancer format cannot auto-apply — decide whether write-ins are advisory-only.

7. **Relationship to existing format machinery.** How does this interact with:
   - `active_set_code()` deriving the latest set from the date (bot/sets.py) — "Latest set" should resolve through this, not a hard-coded code.
   - The daily launcher's open "per-slot format override" fork (lazy vs `/draft`-committed) — the preference/poll system likely subsumes this rather than sitting beside it.
   - The parked Peasant Cube / CubeCobra `importCube` plan — "Cube" as a poll option needs a concrete cube to import.
   - `/pod-settings` format change and `set_code` on `PodDraftEvent` — the poll outcome must write through the same setter so the lobby and card stay consistent.

## Startup prompt for the next session

> We're designing the Pod Format Preference + Format Poll feature (spec/pod-format-poll.md). It has two parts: a format preference players set when they RSVP (Latest set / Flashback set / Cube), and a Sesh-style format poll in the pod thread with those options plus specific choices and player-added write-ins, seeded from the aggregated signup preferences. I have a Sesh poll screenshot to share for the UI style. Before proposing a build plan, walk me through the open questions in the spec one at a time — preference scope, poll resolution (auto-apply vs advisory), category-to-concrete mapping, custom vs native poll, timing/placement, write-in rules, and how it ties into active_set_code, the per-slot format override fork, the Peasant Cube plan, and the /pod-settings format setter. Ask me each fork, take my answer, then write the design.
