import { Fragment, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "../lib/utils";
import { useIsMobile } from "../lib/use-is-mobile";
import {
  hasActiveFilters,
  isCardFilteredOut,
  isCardTrendDimmed,
  TIER_ORDER,
  TREND_COLOR,
  TREND_GLYPH,
  TREND_LABEL,
  trendSteps,
  useTierList,
  type Grader,
  type TierCard,
  type TierFilters,
} from "../data/tierList";

const RARITY_ACCENT: Record<string, string> = {
  C: "#ffffff",
  U: "#707883",
  R: "#a58e4a",
  M: "#bf4427",
};

// Grid columns: lands fold into the colorless column, so there are seven, not eight.
const COLUMN_CODES = ["W", "U", "B", "R", "G", "M", "C"];
const COLUMN_MS: Record<string, string> = {
  W: "w",
  U: "u",
  B: "b",
  R: "r",
  G: "g",
  M: "multicolor",
  C: "c",
};
const COLUMN_NAMES: Record<string, string> = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
  M: "Multicolor",
  C: "Colorless",
};

const columnOf = (color: string) => (color === "L" ? "C" : color);

// Multicolor renders as mana-font's gold duotone glyph (no cost disc), matching untapped.gg.
function columnPipClass(code: string): string {
  if (code === "M") return "ms ms-multicolor ms-duo ms-duo-color ms-grad";
  return `ms ms-cost ms-${COLUMN_MS[code]}`;
}

// Green (top) → red (bottom) accent down the grade column; SB/TBD stay neutral.
const MAIN_TIERS = TIER_ORDER.filter((t) => t !== "SB" && t !== "TBD");
function tierColor(tier: string): string {
  const i = MAIN_TIERS.indexOf(tier);
  if (i === -1) return "#4a5260";
  const hue = Math.round(130 - (130 * i) / (MAIN_TIERS.length - 1));
  return `hsl(${hue}, 62%, 47%)`;
}

export function TierGrid({
  uid,
  graders,
  filters,
  stickyTop,
}: {
  uid: string;
  graders: Grader[];
  filters: TierFilters;
  stickyTop: number;
}) {
  const { data, isLoading, isError } = useTierList(uid, graders);
  const isMobile = useIsMobile();

  if (isLoading || isError || !data) {
    return (
      <div className="border border-border bg-surface py-16 text-center text-muted text-[14px]">
        {isLoading ? "Loading tier list…" : "Couldn't load this tier list."}
      </div>
    );
  }

  const byKey = new Map<string, TierCard[]>();
  for (const card of data) {
    const key = `${columnOf(card.color)}|${card.tier}`;
    const bucket = byKey.get(key);
    if (bucket) {
      bucket.push(card);
    } else {
      byKey.set(key, [card]);
    }
  }
  for (const bucket of byKey.values()) {
    bucket.sort((a, b) => {
      const sa = a.sort_key ?? Number.MAX_SAFE_INTEGER;
      const sb = b.sort_key ?? Number.MAX_SAFE_INTEGER;
      return sa - sb || a.name.localeCompare(b.name);
    });
  }

  return isMobile ? (
    <MobileTiers byKey={byKey} filters={filters} />
  ) : (
    <DesktopGrid byKey={byKey} filters={filters} stickyTop={stickyTop} />
  );
}

function DesktopGrid({
  byKey,
  filters,
  stickyTop,
}: {
  byKey: Map<string, TierCard[]>;
  filters: TierFilters;
  stickyTop: number;
}) {
  const filtering = hasActiveFilters(filters);
  const columnHasHit = (code: string) => {
    if (!filtering) return true;
    return TIER_ORDER.some((tier) =>
      (byKey.get(`${code}|${tier}`) ?? []).some(
        (card) => !isCardFilteredOut(card, filters),
      ),
    );
  };
  const headerCell = {
    position: "sticky",
    top: stickyTop,
    zIndex: 10,
  } as const;
  const tierHasAnyCard = (tier: string) =>
    COLUMN_CODES.some(
      (code) => (byKey.get(`${code}|${tier}`) ?? []).length > 0,
    );
  const tiers = TIER_ORDER.filter(
    (tier) => tier !== "TBD" || tierHasAnyCard(tier),
  );

  return (
    <div className="border-x border-b border-border bg-surface">
      <div
        className="grid"
        style={{ gridTemplateColumns: "48px repeat(7, minmax(0, 1fr))" }}
      >
        <div
          className="border-t border-b border-border bg-bg"
          style={headerCell}
        />
        {COLUMN_CODES.map((code) => (
          <div
            key={code}
            title={COLUMN_NAMES[code]}
            className="border-t border-b border-border bg-bg flex items-center justify-center py-2"
            style={headerCell}
          >
            <i
              className={cn(
                columnPipClass(code),
                "transition-opacity",
                !columnHasHit(code) && "opacity-20",
              )}
              style={{
                fontSize: code === "M" ? 21 : 14,
                filter: columnHasHit(code) ? undefined : "grayscale(1)",
              }}
              aria-label={COLUMN_NAMES[code]}
            />
          </div>
        ))}

        {tiers.map((tier) => (
          <Fragment key={tier}>
            <div
              className="border-b border-l-4 border-border bg-bg flex items-center justify-center font-display text-[20px] leading-none text-text"
              style={{ borderLeftColor: tierColor(tier) }}
            >
              {tier}
            </div>
            {COLUMN_CODES.map((code) => {
              const bucket = byKey.get(`${code}|${tier}`) ?? [];
              return (
                <div
                  key={code}
                  className="border-b border-border p-1 flex flex-col gap-1 min-h-[26px]"
                >
                  {bucket
                    .filter((card) => !isCardFilteredOut(card, filters))
                    .map((card) => (
                      <CardBar
                        key={card.card_id}
                        card={card}
                        mobile={false}
                        dimmed={isCardTrendDimmed(card, filters)}
                      />
                    ))}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function MobileTiers({
  byKey,
  filters,
}: {
  byKey: Map<string, TierCard[]>;
  filters: TierFilters;
}) {
  const filtering = hasActiveFilters(filters);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const visibleTiers = TIER_ORDER.map((tier) => ({
    tier,
    colors: COLUMN_CODES.filter((code) => {
      const bucket = byKey.get(`${code}|${tier}`) ?? [];
      if (bucket.length === 0) return false;
      return filtering
        ? bucket.some((card) => !isCardFilteredOut(card, filters))
        : true;
    }),
  })).filter((t) => t.colors.length > 0);

  const visibleCards = visibleTiers.flatMap(({ tier, colors }) =>
    colors.flatMap((code) =>
      (byKey.get(`${code}|${tier}`) ?? []).filter(
        (card) => !isCardFilteredOut(card, filters),
      ),
    ),
  );
  const selectedIndex = visibleCards.findIndex(
    (card) => card.card_id === selectedId,
  );
  const selectedCard =
    selectedIndex === -1 ? null : visibleCards[selectedIndex];
  const stepTo = (index: number) =>
    setSelectedId(visibleCards[index].card_id);

  return (
    <div className="flex flex-col gap-[5px]">
      {visibleTiers.map(({ tier, colors }) => (
        <div key={tier} className="border border-border bg-surface">
          <div className="bg-bg border-b border-border py-1.5 text-center font-display text-[18px] leading-none text-text">
            {tier}
          </div>
          <div
            className="border-l-4 border-border"
            style={{ borderLeftColor: tierColor(tier) }}
          >
            {colors.map((code, idx) => (
              <div
                key={code}
                className={cn("flex", idx > 0 && "border-t border-border")}
              >
                <div className="w-[44px] shrink-0 flex items-center justify-center">
                  <i
                    className={columnPipClass(code)}
                    style={{ fontSize: code === "M" ? 24 : 16 }}
                    aria-label={COLUMN_NAMES[code]}
                  />
                </div>
                <div className="grid min-w-0 flex-1 grid-cols-1 min-[450px]:grid-cols-2 gap-1 p-1">
                  {(byKey.get(`${code}|${tier}`) ?? [])
                    .filter((card) => !isCardFilteredOut(card, filters))
                    .map((card) => (
                      <CardBar
                        key={card.card_id}
                        card={card}
                        mobile
                        dimmed={isCardTrendDimmed(card, filters)}
                        onOpen={() => setSelectedId(card.card_id)}
                      />
                    ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {selectedCard &&
        createPortal(
          <CardModal
            card={selectedCard}
            onClose={() => setSelectedId(null)}
            onPrev={selectedIndex > 0 ? () => stepTo(selectedIndex - 1) : undefined}
            onNext={
              selectedIndex < visibleCards.length - 1
                ? () => stepTo(selectedIndex + 1)
                : undefined
            }
            position={`${selectedIndex + 1} / ${visibleCards.length}`}
          />,
          document.body,
        )}
    </div>
  );
}

const PREVIEW_W = 260;
const PREVIEW_RATIO = 1.4;
const PREVIEW_GAP = 12;
const PREVIEW_EXTRAS_H = 60;
const PREVIEW_MAT = "#1d2330";

const TEXT_OUTLINE =
  "[text-shadow:1px_1px_1px_rgba(0,0,0,0.85),-1px_-1px_1px_rgba(0,0,0,0.85),1px_-1px_1px_rgba(0,0,0,0.85),-1px_1px_1px_rgba(0,0,0,0.85)]";

interface PreviewAnchor {
  left: number;
  top: number;
  onRight: boolean;
  arrowTop: number;
}

function CardBar({
  card,
  mobile,
  dimmed = false,
  onOpen,
}: {
  card: TierCard;
  mobile: boolean;
  dimmed?: boolean;
  onOpen?: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [anchor, setAnchor] = useState<PreviewAnchor | null>(null);
  const accent = RARITY_ACCENT[card.rarity] ?? RARITY_ACCENT.C;
  const art = card.url.replace("/large/", "/art_crop/");
  const badges = `${card.comment ? "💬" : ""}${card.flags.synergy ? "🤝" : ""}${card.flags.buildaround ? "🛠️" : ""}`;
  const trendLabel = card.trend
    ? `${TREND_LABEL[card.trend]}${card.trend_from ? ` (${card.trend_from} → ${card.tier})` : ""}`
    : "";

  const openPreview = () => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const previewH = PREVIEW_W * PREVIEW_RATIO + PREVIEW_EXTRAS_H;
    const centerY = rect.top + rect.height / 2;
    const top = Math.min(
      Math.max(centerY - previewH / 2, 8),
      Math.max(window.innerHeight - previewH - 8, 8),
    );
    const onRight =
      rect.right + PREVIEW_GAP + PREVIEW_W <= window.innerWidth - 8;
    const left = onRight
      ? rect.right + PREVIEW_GAP
      : rect.left - PREVIEW_GAP - PREVIEW_W;
    const arrowTop = Math.min(Math.max(centerY - top, 14), previewH - 14);
    setAnchor({ left, top, onRight, arrowTop });
  };

  return (
    <div
      ref={ref}
      onMouseEnter={mobile ? undefined : openPreview}
      onMouseLeave={mobile ? undefined : () => setAnchor(null)}
      onClick={mobile ? onOpen : undefined}
      className={cn(
        "relative min-[450px]:max-w-[300px] rounded-[5px] border-l-4",
        mobile && "cursor-pointer",
        dimmed && "opacity-35 grayscale",
      )}
      style={{ borderLeftColor: accent }}
    >
      <div className="relative min-h-[28px] overflow-hidden rounded-r-[5px]">
        <img
          src={art}
          alt=""
          loading="lazy"
          className="absolute inset-0 h-full w-full object-cover"
          style={{ objectPosition: "center 22%" }}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/55 to-black/30" />
        <div className="relative flex min-h-[28px] items-center justify-between gap-1 px-2 py-0.5">
          <span className="flex min-w-0 flex-1 items-center gap-1">
            {card.trend && (
              <span
                className={cn(
                  "flex shrink-0 flex-col items-center",
                  TEXT_OUTLINE,
                )}
                style={{ color: TREND_COLOR[card.trend] }}
                title={trendLabel}
                aria-label={trendLabel}
              >
                {trendGlyphStack(card).map((char, i, stack) => (
                  <span
                    key={i}
                    className={cn(
                      "relative text-[13px] leading-none",
                      i > 0 && "-mt-[6px]",
                    )}
                    style={{ zIndex: stack.length - i }}
                  >
                    {char}
                  </span>
                ))}
              </span>
            )}
            <span
              className={cn(
                "min-w-0 line-clamp-2 text-[13px] font-medium leading-tight text-white",
                TEXT_OUTLINE,
                mobile && "underline decoration-dotted underline-offset-2",
              )}
            >
              {card.name}
            </span>
          </span>
          {badges && (
            <span className="shrink-0 text-[14px] leading-none">{badges}</span>
          )}
        </div>
      </div>
      {anchor &&
        createPortal(
          <CardPreview card={card} anchor={anchor} />,
          document.body,
        )}
    </div>
  );
}

function trendGlyphStack(card: TierCard): string[] {
  if (!card.trend) return [];
  const char = TREND_GLYPH[card.trend];
  return Array.from({ length: Math.min(trendSteps(card), 3) }, () => char);
}

function GradesPanel({ card }: { card: TierCard }) {
  const graders = card.graders ?? [];
  return (
    <div className="flex items-stretch px-3 py-2.5">
      <GradeCell caption="Set review" tier={card.trend_from ?? card.tier} />
      {card.trend ? (
        <GradeCell caption="Updated" tier={card.tier} trend={card.trend} />
      ) : (
        graders.length > 0 && (
          <span className="grid flex-1 grid-cols-[auto_auto] content-center items-center justify-center gap-x-4 gap-y-1.5">
            {graders.map((grade) => (
              <Fragment key={grade.name}>
                <span
                  className={cn(
                    "text-[13px] font-semibold leading-none text-white",
                    TEXT_OUTLINE,
                  )}
                >
                  {grade.name}
                </span>
                <span
                  className={cn(
                    "justify-self-start font-display text-[17px] leading-none",
                    TEXT_OUTLINE,
                  )}
                  style={{ color: tierColor(grade.tier) }}
                >
                  {grade.tier}
                </span>
              </Fragment>
            ))}
          </span>
        )
      )}
    </div>
  );
}

function GradeCell({
  caption,
  tier,
  trend,
}: {
  caption: string;
  tier: string;
  trend?: "up" | "down" | null;
}) {
  return (
    <span className="flex flex-1 flex-col items-center gap-2">
      <span
        className={cn(
          "text-[12px] font-semibold uppercase tracking-[0.1em] leading-none text-white",
          TEXT_OUTLINE,
        )}
      >
        {caption}
      </span>
      <span className="flex items-center gap-1.5">
        <span
          className={cn("font-display text-[26px] leading-none", TEXT_OUTLINE)}
          style={{ color: tierColor(tier) }}
        >
          {tier}
        </span>
        {trend && (
          <span
            className={cn("text-[11px] leading-none", TEXT_OUTLINE)}
            style={{ color: TREND_COLOR[trend] }}
          >
            {TREND_GLYPH[trend]}
          </span>
        )}
      </span>
    </span>
  );
}

function CardPreview({
  card,
  anchor,
}: {
  card: TierCard;
  anchor: PreviewAnchor;
}) {
  const g = PREVIEW_GAP;
  const triangle = anchor.onRight
    ? `M${g} 0 L0 11 L${g} 22 Z`
    : `M0 0 L${g} 11 L0 22 Z`;
  const triangleInner = anchor.onRight
    ? `M${g} 1.4 L1.6 11 L${g} 20.6 Z`
    : `M0 1.4 L${g - 1.6} 11 L0 20.6 Z`;
  return (
    <div
      className="pointer-events-none fixed z-[100]"
      style={{ left: anchor.left, top: anchor.top, width: PREVIEW_W }}
    >
      <svg
        width={g}
        height="22"
        viewBox={`0 0 ${g} 22`}
        className="absolute z-10"
        style={{
          top: anchor.arrowTop - 11,
          ...(anchor.onRight ? { left: -(g - 1) } : { right: -(g - 1) }),
        }}
      >
        <path d={triangle} fill="#fff" fillOpacity="0.6" />
        <path d={triangleInner} fill={PREVIEW_MAT} />
      </svg>
      <div
        className="flex flex-col rounded-xl border border-white/60 p-[6px] shadow-2xl"
        style={{ backgroundColor: PREVIEW_MAT }}
      >
        <GradesPanel card={card} />
        <img src={card.url} alt="" className="w-full rounded-[10px]" />
        {card.comment && (
          <p className="whitespace-pre-line px-3 py-2.5 text-center text-[14px] leading-snug text-text">
            {card.comment}
          </p>
        )}
      </div>
    </div>
  );
}

function CardModal({
  card,
  onClose,
  onPrev,
  onNext,
  position,
}: {
  card: TierCard;
  onClose: () => void;
  onPrev?: () => void;
  onNext?: () => void;
  position?: string;
}) {
  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-6"
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <div
        className="w-full max-w-[320px] rounded-xl border border-white/60 p-[6px] shadow-2xl"
        style={{ backgroundColor: PREVIEW_MAT }}
        onClick={(e) => e.stopPropagation()}
      >
        <GradesPanel card={card} />
        <img src={card.url} alt={card.name} className="w-full rounded-[10px]" />
        {card.comment && (
          <p className="whitespace-pre-line px-3 py-2.5 text-[14px] leading-snug text-text">
            {card.comment}
          </p>
        )}
        <div className="flex items-center justify-between border-t border-white/20 px-3 py-2">
          <ModalNavButton label="Previous card" glyph="‹" onClick={onPrev} />
          {position && (
            <span className="mono text-[12px] tracking-[0.1em] text-white/70">
              {position}
            </span>
          )}
          <ModalNavButton label="Next card" glyph="›" onClick={onNext} />
        </div>
      </div>
    </div>
  );
}

function ModalNavButton({
  label,
  glyph,
  onClick,
}: {
  label: string;
  glyph: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      aria-label={label}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded border border-white/40 text-[22px] leading-none text-text transition-colors",
        onClick ? "hover:bg-white/10" : "opacity-30",
      )}
    >
      {glyph}
    </button>
  );
}
