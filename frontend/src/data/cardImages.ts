import { useEffect, useMemo, useState } from "react";

// Card art is resolved through Scryfall's batch `cards/collection` endpoint keyed by name+set, which
// returns each card's default printing and a direct cards.scryfall.io CDN image URL. The CDN is not
// rate-limited like the REST API, so a whole draft grid loads from one or two batched requests instead
// of dozens of concurrent per-image API hits that Scryfall throttles (and whose failures fall back to
// alternate-art printings).

function cardImageKey(name: string | null | undefined, set: string | null | undefined): string {
  return `${(name ?? "").trim().toLowerCase()}|${(set ?? "").trim().toLowerCase()}`;
}

function namedImageUrl(name: string, set?: string): string {
  const setParam = set ? `&set=${set.toLowerCase()}` : "";
  return `https://api.scryfall.com/cards/named?exact=${encodeURIComponent(name)}${setParam}&format=image&version=normal`;
}

// Direct-API fallbacks for cards the collection batch has not resolved yet or could not match. Both hit
// the rate-limited endpoint, so they only ever cover a handful of misses, never a full grid.
function cardImageFallbacks(name: string | null | undefined, set: string | null | undefined): string[] {
  if (!name) {
    return [];
  }
  const urls = [set ? namedImageUrl(name, set) : null, namedImageUrl(name)];
  return urls.filter((url): url is string => url != null);
}

interface CardImageItem {
  name: string | null;
  set: string | null;
}

// `settled` gates the direct-API fallbacks: while the batch is still resolving, unresolved cards show a
// placeholder rather than firing per-card API requests that the batch is about to make redundant.
export interface CardImages {
  images: Map<string, string>;
  settled: boolean;
}

export function resolvedCardImage(
  cardImages: CardImages,
  name: string | null | undefined,
  set: string | null | undefined,
): string | undefined {
  return cardImages.images.get(cardImageKey(name, set));
}

// The `<img>` src candidates for a card, best first: the batched default-printing CDN URL, then the
// direct-API fallbacks. While the batch is unsettled an unresolved card yields nothing, so it shows a
// placeholder instead of hitting the rate-limited API.
export function cardImageSources(
  cardImages: CardImages,
  name: string | null | undefined,
  set: string | null | undefined,
): string[] {
  const resolved = resolvedCardImage(cardImages, name, set);
  if (resolved) {
    return [resolved, ...cardImageFallbacks(name, set)];
  }
  return cardImages.settled ? cardImageFallbacks(name, set) : [];
}

// Populated default-printing CDN URLs, shared across every viewer so revisiting a draft or opening a
// deck reuses what earlier views already resolved.
const cdnCache = new Map<string, string>();

export function useCardImages(items: CardImageItem[]): CardImages {
  const [images, setImages] = useState<Map<string, string>>(() => new Map(cdnCache));
  const [settled, setSettled] = useState(false);

  const needed = useMemo(() => {
    const byKey = new Map<string, ScryfallIdentifier>();
    for (const item of items) {
      if (!item.name || !item.set) {
        continue;
      }
      const key = cardImageKey(item.name, item.set);
      if (!cdnCache.has(key) && !byKey.has(key)) {
        byKey.set(key, { name: item.name, set: item.set.toLowerCase() });
      }
    }
    return [...byKey.values()];
  }, [items]);

  useEffect(() => {
    if (needed.length === 0) {
      setSettled(true);
      return;
    }
    let cancelled = false;
    setSettled(false);
    resolveCardImages(needed).then(() => {
      if (!cancelled) {
        setImages(new Map(cdnCache));
        setSettled(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [needed]);

  return useMemo(() => ({ images, settled }), [images, settled]);
}

interface ScryfallIdentifier {
  name: string;
  set: string;
}

interface ScryfallCard {
  name: string;
  set: string;
  image_uris?: { normal?: string };
  card_faces?: { image_uris?: { normal?: string } }[];
}

const COLLECTION_ENDPOINT = "https://api.scryfall.com/cards/collection";
const COLLECTION_LIMIT = 75;

// Batches queue behind one another so concurrent viewers never burst past Scryfall's 10 req/s cap.
let queue: Promise<void> = Promise.resolve();

function resolveCardImages(identifiers: ScryfallIdentifier[]): Promise<void> {
  const run = async () => {
    for (let i = 0; i < identifiers.length; i += COLLECTION_LIMIT) {
      await fetchCollectionChunk(identifiers.slice(i, i + COLLECTION_LIMIT));
    }
  };
  queue = queue.then(run, run);
  return queue;
}

async function fetchCollectionChunk(identifiers: ScryfallIdentifier[]): Promise<void> {
  try {
    const res = await fetch(COLLECTION_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifiers }),
    });
    if (!res.ok) {
      return;
    }
    const body = (await res.json()) as { data?: ScryfallCard[] };
    for (const card of body.data ?? []) {
      const url = normalImageUrl(card);
      if (url) {
        cdnCache.set(cardImageKey(card.name, card.set), url);
      }
    }
  } catch {
    // Leave these cards to the per-card API fallbacks.
  }
}

function normalImageUrl(card: ScryfallCard): string | null {
  if (card.image_uris?.normal) {
    return card.image_uris.normal;
  }
  return card.card_faces?.[0]?.image_uris?.normal ?? null;
}
