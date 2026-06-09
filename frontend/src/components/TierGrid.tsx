import { Fragment, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "../lib/utils";
import { useIsMobile } from "../lib/use-is-mobile";
import {
  hasActiveFilters,
  isCardFilteredOut,
  TIER_ORDER,
  useTierList,
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
const COLUMN_MS: Record<string, string> = { W: "w", U: "u", B: "b", R: "r", G: "g", M: "multicolor", C: "c" };
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

export function TierGrid({ uid, filters, stickyTop }: { uid: string; filters: TierFilters; stickyTop: number }) {
  const { data, isLoading, isError } = useTierList(uid);
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
      (byKey.get(`${code}|${tier}`) ?? []).some((card) => !isCardFilteredOut(card, filters)),
    );
  };
  const headerCell = { position: "sticky", top: stickyTop, zIndex: 10 } as const;
  const tierHasAnyCard = (tier: string) => COLUMN_CODES.some((code) => (byKey.get(`${code}|${tier}`) ?? []).length > 0);
  const tiers = TIER_ORDER.filter((tier) => tier !== "TBD" || tierHasAnyCard(tier));

  return (
    <div className="border-x border-b border-border bg-surface">
      <div className="grid" style={{ gridTemplateColumns: "48px repeat(7, minmax(0, 1fr))" }}>
        <div className="border-t border-b border-border bg-bg" style={headerCell} />
        {COLUMN_CODES.map((code) => (
          <div
            key={code}
            title={COLUMN_NAMES[code]}
            className="border-t border-b border-border bg-bg flex items-center justify-center py-2"
            style={headerCell}
          >
            <i
              className={cn(columnPipClass(code), "transition-opacity", !columnHasHit(code) && "opacity-20")}
              style={{ fontSize: code === "M" ? 21 : 14, filter: columnHasHit(code) ? undefined : "grayscale(1)" }}
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
                <div key={code} className="border-b border-border p-1 flex flex-col gap-1 min-h-[26px]">
                  {bucket
                    .filter((card) => !isCardFilteredOut(card, filters))
                    .map((card) => (
                      <CardBar key={card.card_id} card={card} mobile={false} />
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

function MobileTiers({ byKey, filters }: { byKey: Map<string, TierCard[]>; filters: TierFilters }) {
  const filtering = hasActiveFilters(filters);
  const visibleTiers = TIER_ORDER.map((tier) => ({
    tier,
    colors: COLUMN_CODES.filter((code) => {
      const bucket = byKey.get(`${code}|${tier}`) ?? [];
      if (bucket.length === 0) return false;
      return filtering ? bucket.some((card) => !isCardFilteredOut(card, filters)) : true;
    }),
  })).filter((t) => t.colors.length > 0);

  return (
    <div className="flex flex-col gap-[5px]">
      {visibleTiers.map(({ tier, colors }) => (
        <div key={tier} className="border border-border bg-surface">
          <div className="bg-bg border-b border-border py-1.5 text-center font-display text-[18px] leading-none text-text">
            {tier}
          </div>
          <div className="border-l-4 border-border" style={{ borderLeftColor: tierColor(tier) }}>
            {colors.map((code, idx) => (
                <div key={code} className={cn("flex", idx > 0 && "border-t border-border")}>
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
                        <CardBar key={card.card_id} card={card} mobile />
                      ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
      ))}
    </div>
  );
}

const PREVIEW_W = 232;
const PREVIEW_RATIO = 1.4;
const PREVIEW_GAP = 12;

interface PreviewAnchor {
  left: number;
  below: boolean;
  arrowLeft: number;
  edge: number;
}

function CardBar({ card, mobile }: { card: TierCard; mobile: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [anchor, setAnchor] = useState<PreviewAnchor | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const accent = RARITY_ACCENT[card.rarity] ?? RARITY_ACCENT.C;
  const art = card.url.replace("/large/", "/art_crop/");
  const badges = `${card.comment ? "💬" : ""}${card.flags.synergy ? "🤝" : ""}${card.flags.buildaround ? "🛠️" : ""}`;

  const openPreview = () => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const previewH = PREVIEW_W * PREVIEW_RATIO;
    const below = window.innerHeight - rect.bottom >= previewH + PREVIEW_GAP + 8;
    const centerX = rect.left + rect.width / 2;
    const left = Math.min(Math.max(centerX - PREVIEW_W / 2, 8), window.innerWidth - PREVIEW_W - 8);
    const edge = below ? rect.bottom + PREVIEW_GAP : window.innerHeight - rect.top + PREVIEW_GAP;
    const arrowLeft = Math.min(Math.max(centerX - left, 14), PREVIEW_W - 14);
    setAnchor({ left, below, arrowLeft, edge });
  };

  return (
    <div
      ref={ref}
      onMouseEnter={mobile ? undefined : openPreview}
      onMouseLeave={mobile ? undefined : () => setAnchor(null)}
      onClick={mobile ? () => setModalOpen(true) : undefined}
      className={cn("relative min-[450px]:max-w-[300px] rounded-[5px] border-l-4", mobile && "cursor-pointer")}
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
          <span
            className={cn(
              "min-w-0 flex-1 line-clamp-2 text-[13px] font-medium leading-tight text-white [text-shadow:1px_1px_1px_rgba(0,0,0,0.85),-1px_-1px_1px_rgba(0,0,0,0.85),1px_-1px_1px_rgba(0,0,0,0.85),-1px_1px_1px_rgba(0,0,0,0.85)]",
              mobile && "underline decoration-dotted underline-offset-2",
            )}
          >
            {card.name}
          </span>
          {badges && <span className="shrink-0 text-[11px] leading-none">{badges}</span>}
        </div>
      </div>
      {anchor && createPortal(<CardPreview card={card} anchor={anchor} />, document.body)}
      {modalOpen && createPortal(<CardModal card={card} onClose={() => setModalOpen(false)} />, document.body)}
    </div>
  );
}

function CardPreview({ card, anchor }: { card: TierCard; anchor: PreviewAnchor }) {
  const g = PREVIEW_GAP;
  const triangle = anchor.below ? `M0 ${g} L11 0 L22 ${g} Z` : `M0 0 L11 ${g} L22 0 Z`;
  return (
    <div
      className="pointer-events-none fixed z-[100]"
      style={{ left: anchor.left, width: PREVIEW_W, ...(anchor.below ? { top: anchor.edge } : { bottom: anchor.edge }) }}
    >
      <svg
        width="22"
        height={g}
        viewBox={`0 0 22 ${g}`}
        className="absolute"
        style={anchor.below ? { top: -(g - 1), left: anchor.arrowLeft - 11 } : { bottom: -(g - 1), left: anchor.arrowLeft - 11 }}
      >
        <path d={triangle} fill="#3b4458" />
      </svg>
      <div className={cn("flex flex-col overflow-hidden rounded-lg border border-border2 bg-surface shadow-2xl", !anchor.below && "flex-col-reverse")}>
        <img src={card.url} alt="" className="w-full" />
        {card.comment && <p className="whitespace-pre-line px-2.5 py-2 text-[12px] leading-snug text-text">{card.comment}</p>}
      </div>
    </div>
  );
}

function CardModal({ card, onClose }: { card: TierCard; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-6"
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <div
        className="w-full max-w-[320px] overflow-hidden rounded-xl border border-border2 bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <img src={card.url} alt={card.name} className="w-full" />
        {card.comment && (
          <p className="whitespace-pre-line px-3 py-2.5 text-[13px] leading-snug text-text">{card.comment}</p>
        )}
      </div>
    </div>
  );
}
