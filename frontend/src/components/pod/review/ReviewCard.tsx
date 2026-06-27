import { useState } from "react";

import { cn } from "../../../lib/utils";
import type { ArtifactCard } from "../../../types/leaderboard";

function scryfallImageUrl(set: string, cn: string): string {
  return `https://api.scryfall.com/cards/${set.toLowerCase()}/${encodeURIComponent(cn)}?format=image&version=normal`;
}

export function CardImage({ card, className }: { card: ArtifactCard; className?: string }) {
  const [failed, setFailed] = useState(false);
  const src = card.s && card.cn ? scryfallImageUrl(card.s, card.cn) : null;
  if (!src || failed) {
    return (
      <div className={cn("flex aspect-[488/680] items-start bg-surface2 p-2", className)}>
        <span className="font-body text-[11px] leading-tight text-subtle">{card.n}</span>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={card.n ?? ""}
      loading="lazy"
      draggable={false}
      onError={() => setFailed(true)}
      className={cn("block aspect-[488/680] w-full object-cover", className)}
    />
  );
}

const COLOR_HEX: Record<string, string> = {
  W: "#f3ecca",
  U: "#4aa8ff",
  B: "#9a8bb0",
  R: "#ff5e5e",
  G: "#2ee85c",
};

export function avatarAccent(colors: string): string {
  const first = [...colors].find((c) => COLOR_HEX[c.toUpperCase()]);
  return first ? COLOR_HEX[first.toUpperCase()] : "#7a8395";
}
