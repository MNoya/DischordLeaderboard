import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { cn } from "../../../lib/utils";
import {
  resolveTierList,
  tierColor,
  TREND_COLOR,
  trendGlyphStack,
  useTierList,
  type TierCard,
} from "../../../data/tierList";
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
  const openPreview = useContext(CardPreviewContext);
  const sources = cardImageSources(card, reviewSet);
  const [sourceIndex, setSourceIndex] = useState(0);
  const src = sources[sourceIndex] ?? null;
  const onContextMenu = openPreview
    ? (e: React.MouseEvent) => {
        e.preventDefault();
        openPreview(card);
      }
    : undefined;
  if (!src) {
    return (
      <div
        onContextMenu={onContextMenu}
        className={cn("flex aspect-[488/680] items-start bg-surface2 p-2", className)}
      >
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
      onContextMenu={onContextMenu}
      className={cn("block aspect-[488/680] w-full object-cover", className)}
    />
  );
}

// A fanned column of overlapping cards where only a `reveal`-px sliver of each covered card shows.
// Hovering that sliver lifts the card to the front; the lifted card's body is click-through so it
// never traps the cursor over the cards beneath it — moving down the sliver strip walks the fan.
export function StackColumn({
  count,
  reveal,
  width,
  className,
  cardClassName,
  glowIndex = null,
  cardAt,
  renderCard,
}: {
  count: number;
  reveal: number;
  width?: number;
  className?: string;
  cardClassName?: string;
  glowIndex?: number | null;
  cardAt?: (i: number) => ArtifactCard | undefined;
  renderCard: (i: number) => React.ReactNode;
}) {
  const openPreview = useContext(CardPreviewContext);
  const [raised, setRaised] = useState<number | null>(null);
  if (count <= 0) {
    return null;
  }
  const style = width != null ? { width } : undefined;
  const onContextMenu = (i: number) => (e: React.MouseEvent) => {
    const card = cardAt?.(i);
    if (card && openPreview) {
      e.preventDefault();
      openPreview(card);
    }
  };
  return (
    <div className={cn("relative [display:flow-root]", className)} style={style}>
      {Array.from({ length: count }, (_, i) => {
        const isLast = i === count - 1;
        const isGlow = i === glowIndex;
        const z = raised === i ? 30 : isGlow ? 10 : undefined;
        const hover = {
          onMouseEnter: () => setRaised(i),
          onMouseLeave: () => setRaised((r) => (r === i ? null : r)),
          onContextMenu: onContextMenu(i),
        };
        if (isLast) {
          return (
            <div
              key={i}
              className={cn("group relative", cardClassName, isGlow && "review-last-pick")}
              style={{ marginTop: (count - 1) * reveal, zIndex: z }}
              {...hover}
            >
              {renderCard(i)}
            </div>
          );
        }
        return (
          <div
            key={i}
            className="group absolute inset-x-0"
            style={{ top: i * reveal, height: reveal, zIndex: z }}
            {...hover}
          >
            <div className={cn("pointer-events-none absolute inset-x-0 top-0", cardClassName, isGlow && "review-last-pick")}>
              {renderCard(i)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Draftmancer-style right-click preview: right-clicking any review card slides a card image in from
// the right edge of the viewport, with the card's Limited grade if the set has a tier list.
const CardPreviewContext = createContext<((card: ArtifactCard) => void) | null>(null);

export function CardPreviewProvider({ setCode, children }: { setCode: string; children: React.ReactNode }) {
  const grades = useReviewGrades(setCode);
  const [preview, setPreview] = useState<ArtifactCard | null>(null);

  const openPreview = useMemo(() => (card: ArtifactCard) => setPreview(card), []);

  useEffect(() => {
    if (!preview) {
      return;
    }
    const close = () => setPreview(null);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close();
      }
    };
    const onPointerDown = (e: PointerEvent) => {
      if (e.button === 0) {
        close();
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onPointerDown, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onPointerDown, true);
    };
  }, [preview]);

  const grade = preview ? grades.get(normalizeCardName(preview.n)) : undefined;
  return (
    <CardPreviewContext.Provider value={openPreview}>
      {children}
      {preview && <CardPreviewOverlay card={preview} grade={grade} />}
    </CardPreviewContext.Provider>
  );
}

const normalizeCardName = (name: string | null | undefined) => (name ?? "").trim().toLowerCase();

function useReviewGrades(setCode: string): Map<string, TierCard> {
  const resolved = resolveTierList(setCode);
  const { data } = useTierList(resolved.effectiveUid, resolved.graders);
  return useMemo(() => {
    const byName = new Map<string, TierCard>();
    for (const card of data ?? []) {
      byName.set(normalizeCardName(card.name), card);
    }
    return byName;
  }, [data]);
}

function CardPreviewOverlay({ card, grade }: { card: ArtifactCard; grade: TierCard | undefined }) {
  const reviewSet = useContext(ReviewSetContext);
  const sources = cardImageSources(card, reviewSet);
  const [sourceIndex, setSourceIndex] = useState(0);
  const src = sources[sourceIndex] ?? null;
  return (
    <div className="pointer-events-none fixed right-10 top-1/2 z-[70] -translate-y-1/2">
      <div className="relative" style={{ animation: "card-preview-in-right 180ms ease-out" }}>
        {src ? (
          <img
            key={src}
            src={src}
            alt={card.n ?? ""}
            draggable={false}
            onError={() => setSourceIndex((i) => i + 1)}
            className="h-[54vh] max-h-[500px] w-auto rounded-xl shadow-2xl outline outline-1 -outline-offset-1 outline-white/20"
          />
        ) : (
          <div className="flex h-[54vh] max-h-[500px] w-[39vh] max-w-[360px] items-center justify-center rounded-xl bg-surface2 p-6 shadow-2xl">
            <span className="font-body text-sm text-subtle">{card.n}</span>
          </div>
        )}
        {grade && <GradeBadge card={grade} />}
      </div>
    </div>
  );
}

function GradeBadge({ card }: { card: TierCard }) {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <div className="flex items-center gap-2.5 rounded-lg bg-black/80 px-3 py-2 backdrop-blur-sm">
        <span className="flex flex-col text-[12px] font-semibold uppercase leading-none tracking-[0.1em] text-white">
          <span>Tier</span>
          <span>List</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="font-display text-[26px] leading-none" style={{ color: tierColor(card.tier) }}>
            {card.tier}
          </span>
          {card.trend && (
            <span className="flex flex-col items-center" style={{ color: TREND_COLOR[card.trend] }}>
              {trendGlyphStack(card).map((char, i, stack) => (
                <span key={i} className={cn("text-[11px] leading-none", i > 0 && "-mt-[5px]")} style={{ zIndex: stack.length - i }}>
                  {char}
                </span>
              ))}
            </span>
          )}
        </span>
      </div>
    </div>
  );
}
