import { createContext, useContext, useState } from "react";

import { cn } from "../../../lib/utils";
import type { ArtifactCard } from "../../../types/leaderboard";

// The draft's main set, a fallback for cards that carry no recorded set. Each card records its own
// set (e.g. `soa` Mystical Archive within an SOS draft); resolving by name against that set yields
// the base printing rather than the recorded collector number, which can be an alternate-art variant.
const ReviewSetContext = createContext<string | null>(null);
export const ReviewSetProvider = ReviewSetContext.Provider;

function scryfallNamedUrl(name: string, set?: string): string {
  const setParam = set ? `&set=${set.toLowerCase()}` : "";
  return `https://api.scryfall.com/cards/named?exact=${encodeURIComponent(name)}${setParam}&format=image&version=normal`;
}

function scryfallNumberUrl(set: string, cn: string): string {
  return `https://api.scryfall.com/cards/${set.toLowerCase()}/${encodeURIComponent(cn)}?format=image&version=normal`;
}

export function cardImageSources(card: ArtifactCard, reviewSet: string | null): string[] {
  const cardSet = card.s ?? reviewSet ?? null;
  const inSet = card.n && cardSet ? scryfallNamedUrl(card.n, cardSet) : null;
  const recorded = card.s && card.cn ? scryfallNumberUrl(card.s, card.cn) : null;
  const anyPrinting = card.n ? scryfallNamedUrl(card.n) : null;
  return [inSet, recorded, anyPrinting].filter((s): s is string => s != null);
}

export function CardImage({ card, className }: { card: ArtifactCard; className?: string }) {
  const reviewSet = useContext(ReviewSetContext);
  const sources = cardImageSources(card, reviewSet);
  const [sourceIndex, setSourceIndex] = useState(0);
  const src = sources[sourceIndex] ?? null;
  if (!src) {
    return (
      <div className={cn("flex aspect-[488/680] items-start bg-surface2 p-2", className)}>
        <span className="font-body text-[11px] leading-tight text-subtle">{card.n}</span>
      </div>
    );
  }
  return (
    <img
      key={src}
      src={src}
      alt={card.n ?? ""}
      loading="lazy"
      draggable={false}
      onError={() => setSourceIndex((i) => i + 1)}
      className={cn("block aspect-[488/680] w-full object-cover", className)}
    />
  );
}
