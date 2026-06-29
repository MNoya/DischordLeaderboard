import { createContext, useContext, useState } from "react";

import { cn } from "../../../lib/utils";
import type { ArtifactCard } from "../../../types/leaderboard";

// The draft's main set. 17lands records each card's actual printing, which may be an alternate-art
// product (e.g. `soa` showcases); resolving by name against this set yields the canonical card face.
const ReviewSetContext = createContext<string | null>(null);
export const ReviewSetProvider = ReviewSetContext.Provider;

function scryfallNamedUrl(name: string, set?: string): string {
  const setParam = set ? `&set=${set.toLowerCase()}` : "";
  return `https://api.scryfall.com/cards/named?exact=${encodeURIComponent(name)}${setParam}&format=image&version=normal`;
}

function scryfallNumberUrl(set: string, cn: string): string {
  return `https://api.scryfall.com/cards/${set.toLowerCase()}/${encodeURIComponent(cn)}?format=image&version=normal`;
}

export function CardImage({ card, className }: { card: ArtifactCard; className?: string }) {
  const reviewSet = useContext(ReviewSetContext);
  const canonicalSet = reviewSet ?? card.s ?? null;
  const inSet = card.n && canonicalSet ? scryfallNamedUrl(card.n, canonicalSet) : null;
  const anyPrinting = card.n ? scryfallNamedUrl(card.n) : null;
  const recorded = card.s && card.cn ? scryfallNumberUrl(card.s, card.cn) : null;
  const sources = [inSet, anyPrinting, recorded].filter((s): s is string => s != null);
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
