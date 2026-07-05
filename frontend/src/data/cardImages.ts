// Base-printing card art straight from Scryfall's named-image endpoint. `named?exact=<name>&set=<set>`
// resolves the set's default printing rather than the drafted alternate-art variant, and the browser
// loads it directly as an `<img>` so cards paint as they arrive with no batch round-trip.

// Double-faced and split cards arrive as "Front // Back", but Scryfall's name lookup matches the front
// face only.
function frontFaceName(name: string): string {
  const separator = name.indexOf("//");
  return (separator === -1 ? name : name.slice(0, separator)).trim();
}

function namedImageUrl(name: string, set?: string): string {
  const setParam = set ? `&set=${set.toLowerCase()}` : "";
  const exact = encodeURIComponent(frontFaceName(name));
  return `https://api.scryfall.com/cards/named?exact=${exact}${setParam}&format=image&version=normal`;
}

// Image URL candidates for a card, best first: pinned to the card's set for the base printing, then any
// printing as a fallback when the set lookup misses.
export function cardImageSources(name: string | null | undefined, set: string | null | undefined): string[] {
  if (!name) {
    return [];
  }
  const urls = [set ? namedImageUrl(name, set) : null, namedImageUrl(name)];
  return urls.filter((url): url is string => url != null);
}
