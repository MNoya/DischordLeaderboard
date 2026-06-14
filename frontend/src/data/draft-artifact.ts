// Client-side derivations over the pod draft artifact (public_pod_draft_log). The deck view reads
// resolveDeck; a future draft-review view reads the same artifact's packs/picks.

import type { Mainboard, MainboardCard, PodDraftArtifact } from "../types/leaderboard";

type ArtifactCard = PodDraftArtifact["cards"][number];

// A seat's built deck (maindeck + sideboard), grouped by name with counts and sorted by mana value.
// Returns null when the event predates deck capture (decks is null) or the seat built nothing. Basics
// are absent — they are never in the drafted pool.
export function resolveDeck(artifact: PodDraftArtifact, seatIndex: number): Mainboard | null {
  const deck = artifact.decks?.[seatIndex];
  if (!deck || deck.main.length === 0) {
    return null;
  }
  const deckSet = dominantSet(artifact, deck.main);
  return {
    set: deckSet,
    cards: resolveCards(artifact, deck.main, deckSet),
    sideboard: resolveCards(artifact, deck.side, deckSet),
  };
}

function dominantSet(artifact: PodDraftArtifact, indices: number[]): string | null {
  const tally = new Map<string, number>();
  for (const idx of indices) {
    const card = artifact.cards[idx];
    if (card?.s) {
      tally.set(card.s, (tally.get(card.s) ?? 0) + 1);
    }
  }
  let dominant: string | null = null;
  let best = 0;
  for (const [code, n] of tally) {
    if (n > best) {
      best = n;
      dominant = code;
    }
  }
  return dominant;
}

function resolveCards(artifact: PodDraftArtifact, indices: number[], deckSet: string | null): MainboardCard[] {
  const grouped = new Map<string, { card: ArtifactCard; count: number }>();
  for (const idx of indices) {
    const card = artifact.cards[idx];
    if (!card || card.n == null) {
      continue;
    }
    const existing = grouped.get(card.n);
    if (existing) {
      existing.count += 1;
    } else {
      grouped.set(card.n, { card, count: 1 });
    }
  }
  return [...grouped.values()]
    .sort((a, b) => (a.card.cmc ?? 99) - (b.card.cmc ?? 99) || a.card.n!.localeCompare(b.card.n!))
    .map(({ card, count }) => {
      const resolved: MainboardCard = { name: card.n!, cn: card.cn, cmc: card.cmc, type: card.type };
      if (card.s && card.s !== deckSet) {
        resolved.set = card.s;
      }
      if (card.c && card.c.length) {
        resolved.colors = card.c;
      }
      if (count > 1) {
        resolved.count = count;
      }
      return resolved;
    });
}
