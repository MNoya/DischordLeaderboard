import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

// Card art comes from our own `/api/card-images` endpoint, which resolves a draft's exact cards to
// base-printing CDN URLs server-side (Scryfall's collection batch, ~75 cards per request) and is
// edge-cached. The browser only ever hits that endpoint and the image CDN, never Scryfall's
// rate-limited API, so whole pools — including a cube spanning dozens of sets — load in a few batched
// requests. Cards are keyed by `<set>|<front-face name>`; the named endpoint covers the rare card the
// batch can't resolve (basics).

export interface CardImageItem {
  name: string | null;
  set: string | null;
}

export interface CardImages {
  images: Map<string, string>;
  ready: boolean;
}

function frontFaceName(name: string): string {
  const separator = name.indexOf("//");
  return (separator === -1 ? name : name.slice(0, separator)).trim();
}

function mapKey(set: string | null | undefined, name: string): string {
  return `${(set ?? "").toLowerCase()}|${frontFaceName(name).toLowerCase()}`;
}

function namedImageUrl(name: string, set?: string): string {
  const setParam = set ? `&set=${set.toLowerCase()}` : "";
  const exact = encodeURIComponent(frontFaceName(name));
  return `https://api.scryfall.com/cards/named?exact=${exact}${setParam}&format=image&version=normal`;
}

function dedupeIdentifiers(items: CardImageItem[]): { name: string; set: string }[] {
  const byKey = new Map<string, { name: string; set: string }>();
  for (const item of items) {
    if (!item.name || !item.set) {
      continue;
    }
    const key = mapKey(item.set, item.name);
    if (!byKey.has(key)) {
      byKey.set(key, { name: item.name, set: item.set });
    }
  }
  return [...byKey.values()];
}

async function fetchCardImages(identifiers: { name: string; set: string }[]): Promise<Record<string, string>> {
  if (identifiers.length === 0) {
    return {};
  }
  const res = await fetch("/api/card-images", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ identifiers }),
  });
  return res.ok ? ((await res.json()) as Record<string, string>) : {};
}

// `<set>|<front-face name>` -> base-printing CDN URL for the given cards, plus a `ready` flag. The
// query is keyed by the card set, so the same draft resolves once per session; the endpoint itself is
// edge-cached across sessions and users.
export function useCardImageMap(items: CardImageItem[]): CardImages {
  const identifiers = useMemo(() => dedupeIdentifiers(items), [items]);
  const signature = useMemo(
    () => identifiers.map((id) => `${id.set.toLowerCase()}|${frontFaceName(id.name).toLowerCase()}`).sort().join(","),
    [identifiers],
  );
  const { data, isPending } = useQuery({
    queryKey: ["card-images", signature],
    queryFn: () => fetchCardImages(identifiers),
    enabled: identifiers.length > 0,
    staleTime: Infinity,
    gcTime: Infinity,
  });
  return useMemo(() => {
    const images = new Map<string, string>(Object.entries(data ?? {}));
    return { images, ready: identifiers.length === 0 || !isPending };
  }, [data, isPending, identifiers.length]);
}

// The `<img>` src candidates for a card, best first: the base-printing CDN URL from the map, then
// Scryfall's named endpoint. While the map is still loading an unresolved card yields nothing (a
// placeholder), so the named fallback only ever covers the few cards a loaded map omits (basics).
export function cardImageSources(
  name: string | null | undefined,
  set: string | null | undefined,
  cardImages?: CardImages,
): string[] {
  if (!name) {
    return [];
  }
  const mapped = cardImages?.images.get(mapKey(set, name));
  const fallback = [set ? namedImageUrl(name, set) : null, namedImageUrl(name)].filter(
    (url): url is string => url != null,
  );
  if (mapped) {
    return [mapped, ...fallback];
  }
  const ready = cardImages?.ready ?? true;
  return ready ? fallback : [];
}
