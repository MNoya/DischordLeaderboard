import { useCallback, useMemo, useState, type ReactNode } from "react";
import { AppHeader } from "../components/AppHeader";
import { SectionLabel } from "../components/SectionLabel";
import { CtaPill } from "../components/CtaPill";
import { DiscordIcon } from "../components/BrandIcons";
import { SetGlyph } from "../components/Brand";
import { ManaCost, Pip } from "../components/ManaPips";
import { cardsMshFixture } from "../data/fixtures/cards-msh";
import { SLOTS, P0P1_SET_CODE, P0P1_SET_NAME, P0P1_VOTING_DEADLINE } from "../data/p0p1Slots";
import type { Card, SlotDefinition, SlotKey } from "../types/p0p1";

interface SlotMeta {
  accent: string;
  pip: ReactNode;
  short: string;
}

const SLOT_META: Record<SlotKey, SlotMeta> = {
  white_common: { accent: "#e8e4cf", pip: <Pip c="W" size={15} />, short: "White" },
  blue_common: { accent: "#5aa9e6", pip: <Pip c="U" size={15} />, short: "Blue" },
  black_common: { accent: "#9b86c4", pip: <Pip c="B" size={15} />, short: "Black" },
  red_common: { accent: "#e0625c", pip: <Pip c="R" size={15} />, short: "Red" },
  green_common: { accent: "#54b87a", pip: <Pip c="G" size={15} />, short: "Green" },
  multicolor_uncommon: { accent: "#ffc63a", pip: <GoldBadge>WU</GoldBadge>, short: "Multi" },
  wildcard_common: { accent: "#7a8395", pip: <WildBadge>C</WildBadge>, short: "Wild C" },
  wildcard_uncommon: { accent: "#9aa3b5", pip: <WildBadge>U</WildBadge>, short: "Wild U" },
};

function GoldBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-full bg-gold/20 text-gold text-[9px] font-bold tracking-tight">
      {children}
    </span>
  );
}

function WildBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-full border border-border2 text-muted text-[10px] font-bold">
      {children}
    </span>
  );
}

function useMockBallot(cards: Card[]) {
  const seed = useMemo(() => {
    const picks: Partial<Record<SlotKey, string>> = {};
    const taken = new Set<string>();
    const fillOrder: SlotKey[] = [
      "white_common",
      "blue_common",
      "black_common",
      "red_common",
      "green_common",
      "multicolor_uncommon",
    ];
    for (const key of fillOrder) {
      const slot = SLOTS.find((s) => s.key === key)!;
      const pick = cards.find((c) => slot.filter(c, taken));
      if (pick) {
        picks[key] = pick.name;
        taken.add(pick.name);
      }
    }
    return picks;
  }, [cards]);

  const [picks, setPicks] = useState<Partial<Record<SlotKey, string>>>(seed);
  const [activeSlot, setActiveSlot] = useState<SlotKey>("wildcard_common");

  const select = useCallback((slot: SlotKey, name: string) => {
    setPicks((prev) => ({ ...prev, [slot]: name }));
    const idx = SLOTS.findIndex((s) => s.key === slot);
    for (let i = 1; i <= SLOTS.length; i++) {
      const next = SLOTS[(idx + i) % SLOTS.length];
      setPicks((prev) => {
        if (!prev[next.key]) setActiveSlot(next.key);
        return prev;
      });
      break;
    }
  }, []);

  const clearAll = useCallback(() => setPicks({}), []);

  return { picks, activeSlot, setActiveSlot, select, clearAll };
}

const cardsByName = new Map(cardsMshFixture.map((c) => [c.name, c]));
const SCORING_SLOTS = SLOTS;

function eligibleFor(slot: SlotDefinition, picks: Partial<Record<SlotKey, string>>): Card[] {
  const taken = new Set(
    Object.entries(picks)
      .filter(([k]) => k !== slot.key)
      .map(([, v]) => v!),
  );
  return cardsMshFixture.filter((c) => slot.filter(c, taken));
}

function Countdown() {
  const diff = P0P1_VOTING_DEADLINE.getTime() - Date.now();
  const days = Math.floor(diff / 86_400_000);
  const hours = Math.floor((diff / 3_600_000) % 24);
  return (
    <span className="text-green whitespace-nowrap">
      Closes in {days} days, {hours} hours
    </span>
  );
}

function ProgressBar({ filled, total = SLOTS.length }: { filled: number; total?: number }) {
  const pct = Math.round((filled / total) * 100);
  const complete = filled === total;
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-surface2 overflow-hidden rounded-full">
        <div
          className={`h-full rounded-full transition-all ${complete ? "bg-green" : "bg-green/70"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`mono text-[12px] shrink-0 ${complete ? "text-green" : "text-muted"}`}>
        {filled}/{total}
      </span>
    </div>
  );
}

function CardGrid({
  slot,
  picks,
  onSelect,
  minColW = 150,
}: {
  slot: SlotDefinition;
  picks: Partial<Record<SlotKey, string>>;
  onSelect: (name: string) => void;
  minColW?: number;
}) {
  const cards = eligibleFor(slot, picks);
  const current = picks[slot.key];
  return (
    <div
      className="grid gap-2"
      style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${minColW}px, 1fr))` }}
    >
      {cards.map((card) => (
        <button
          type="button"
          key={card.name}
          onClick={() => onSelect(card.name)}
          className={`bg-transparent border-2 transition-colors cursor-pointer p-0 rounded-lg overflow-hidden ${
            current === card.name ? "border-green" : "border-transparent hover:border-green"
          }`}
        >
          <img
            src={card.imageNormal}
            alt={card.name}
            className="w-full block"
            style={{ aspectRatio: "488 / 680" }}
            loading="lazy"
          />
        </button>
      ))}
    </div>
  );
}

function LoginCta() {
  return (
    <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
      LOG IN TO SUBMIT PICKS
    </CtaPill>
  );
}

export function P0P1MocksPage() {
  const params = new URLSearchParams(window.location.search);
  const embed = params.has("embed");
  const only = params.get("only");
  const [viewport, setViewport] = useState<"desktop" | "mobile">("desktop");

  const mobile = params.get("m");
  if (embed) {
    if (mobile === "selector") {
      return <MobileSelector />;
    }
    if (mobile === "list") {
      return <MobileList />;
    }
    return (
      <div className="bg-bg text-text min-h-screen">
        <AppHeader subtitle="Pack 0, Pick 1" />
        {(!only || only === "a") && <DirectionA embedded />}
        {(!only || only === "b") && <DirectionB embedded />}
        {(!only || only === "c") && <DirectionC embedded />}
        <div className="h-10" />
      </div>
    );
  }

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col">
      <AppHeader subtitle="Pack 0, Pick 1 — Mocks" />
      <div className="sticky top-0 z-30 bg-bg/95 backdrop-blur border-b border-border px-10 py-2 flex items-center gap-4 text-[13px]">
        <span className="font-display tracking-[0.12em] text-muted">DESKTOP DIRECTIONS</span>
        {viewport === "desktop" && (
          <>
            <a href="#dir-a" className="text-green hover:underline">A · Polished rail</a>
            <a href="#dir-b" className="text-green hover:underline">B · Roster strip</a>
            <a href="#dir-c" className="text-green hover:underline">C · Team board</a>
          </>
        )}
        <div className="ml-auto flex items-center border border-border2">
          {(["desktop", "mobile"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setViewport(v)}
              className={`px-3 py-1 font-display tracking-[0.1em] text-[12px] transition-colors ${
                viewport === v ? "bg-green text-bg" : "bg-transparent text-muted hover:text-text"
              }`}
            >
              {v.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {viewport === "desktop" ? (
        <>
          <DirectionA />
          <DirectionB />
          <DirectionC />
          <div className="h-20" />
        </>
      ) : (
        <MobilePreview />
      )}
    </div>
  );
}

function MobilePreview() {
  const frames: { n: string; title: string; desc: string; m: string }[] = [
    { n: "M1", title: "Sticky selector", desc: "8 team chips in two rows pinned at top, tiebreaker separated, cards inline below", m: "selector" },
    { n: "M2", title: "Slot list + sheet", desc: "Full pick list with names + intro copy, tiebreaker separated, tap a slot to pick", m: "list" },
  ];
  return (
    <div className="flex flex-wrap gap-12 justify-center px-10 py-10">
      {frames.map((f) => (
        <div key={f.m} className="flex flex-col items-center gap-3">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-green text-[22px] leading-none">{f.n}</span>
            <span className="font-display text-[16px] tracking-[0.04em]">{f.title}</span>
          </div>
          <p className="text-muted text-[12px] max-w-[300px] text-center leading-[1.5]">{f.desc}</p>
          <div className="rounded-[28px] border-[6px] border-border2 bg-black overflow-hidden shadow-2xl">
            <iframe
              title={f.title}
              src={`/p0p1-mocks?embed=1&m=${f.m}`}
              className="block bg-bg"
              style={{ width: 390, height: 800 }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function MobileChip({
  slot,
  card,
  active,
  onClick,
}: {
  slot: SlotDefinition;
  card: Card | undefined;
  active: boolean;
  onClick: () => void;
}) {
  const meta = SLOT_META[slot.key];
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={slot.label}
      className={`relative w-full aspect-[5/4] bg-surface2 overflow-hidden border transition-colors ${
        active ? "border-green ring-1 ring-green" : "border-border2"
      }`}
    >
      <div className="absolute top-0 left-0 right-0 h-[3px] z-10" style={{ background: meta.accent }} />
      {card ? (
        <img src={card.imageArtCrop} alt="" className="w-full h-full object-cover" />
      ) : (
        <span className="absolute inset-0 flex items-center justify-center">{meta.pip}</span>
      )}
    </button>
  );
}

function MobileSelector() {
  const ballot = useMockBallot(cardsMshFixture);
  const filledScoring = SCORING_SLOTS.filter((s) => ballot.picks[s.key]).length;
  const activeSlot = SLOTS.find((s) => s.key === ballot.activeSlot)!;
  return (
    <div className="bg-bg text-text min-h-screen flex flex-col">
      <AppHeader subtitle="Pack 0, Pick 1" />
      <div className="sticky top-0 z-20 bg-bg border-b border-border px-3 pt-2.5 pb-2.5">
        <div className="flex items-center justify-between mb-1">
          <span className="font-display text-[18px] tracking-[0.04em]">
            {P0P1_SET_CODE} <span className="text-muted text-[12px]">PACK 0, PICK 1</span>
          </span>
          <span className="text-[12px]">
            <Countdown />
          </span>
        </div>
        <p className="text-subtle text-[12.5px] leading-[1.45] mb-2">
          Build a team of 8 cards. After {P0P1_SET_CODE} runs six weeks, teams are ranked by their total 17Lands GIH
          win rate.
        </p>
        <div className="mb-2.5">
          <ProgressBar filled={filledScoring} total={8} />
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          {SCORING_SLOTS.map((slot) => (
            <MobileChip
              key={slot.key}
              slot={slot}
              card={ballot.picks[slot.key] ? cardsByName.get(ballot.picks[slot.key]!) : undefined}
              active={ballot.activeSlot === slot.key}
              onClick={() => ballot.setActiveSlot(slot.key)}
            />
          ))}
        </div>
      </div>

      <div className="flex-1 px-3 pt-3 pb-24">
        <div className="flex items-center gap-2 mb-2.5">
          {SLOT_META[activeSlot.key].pip}
          <span className="font-display text-[18px] tracking-[0.06em]">{activeSlot.label}</span>
        </div>
        <input
          placeholder="Search cards..."
          className="w-full bg-surface border border-border2 px-3 py-2 text-[14px] outline-none focus:border-green mb-3"
        />
        <CardGrid slot={activeSlot} picks={ballot.picks} onSelect={(n) => ballot.select(activeSlot.key, n)} minColW={150} />
      </div>

      <MobileSubmitBar filled={filledScoring} total={8} />
    </div>
  );
}

function MobileList() {
  const ballot = useMockBallot(cardsMshFixture);
  const filledScoring = SCORING_SLOTS.filter((s) => ballot.picks[s.key]).length;
  const [sheetSlot, setSheetSlot] = useState<SlotKey | null>(null);
  const activeSlot = sheetSlot ? SLOTS.find((s) => s.key === sheetSlot)! : null;
  return (
    <div className="bg-bg text-text min-h-screen flex flex-col">
      <AppHeader subtitle="Pack 0, Pick 1" />
      <div className="px-3 pt-3 pb-24">
        <div className="flex items-center justify-between mb-1">
          <span className="font-display text-[20px] tracking-[0.04em]">
            {P0P1_SET_CODE} <span className="text-muted text-[12px]">PACK 0, PICK 1</span>
          </span>
          <span className="text-[12px]">
            <Countdown />
          </span>
        </div>
        <p className="text-subtle text-[13px] leading-[1.5] mb-3">
          Build a team of 8 cards you think will perform best in {P0P1_SET_CODE}. After six weeks, teams are ranked by
          their total 17Lands GIH win rate.
        </p>
        <div className="mb-3">
          <ProgressBar filled={filledScoring} total={8} />
        </div>
        <div className="flex flex-col gap-1.5">
          {SCORING_SLOTS.map((slot) => (
            <SlotRow
              key={slot.key}
              slot={slot}
              card={ballot.picks[slot.key] ? cardsByName.get(ballot.picks[slot.key]!) : undefined}
              active={false}
              onClick={() => setSheetSlot(slot.key)}
            />
          ))}
        </div>
      </div>

      <MobileSubmitBar filled={filledScoring} total={8} />

      {activeSlot && (
        <div className="fixed inset-0 z-50 bg-bg flex flex-col">
          <div className="flex items-center gap-2 px-3 py-3 border-b border-border">
            {SLOT_META[activeSlot.key].pip}
            <span className="font-display text-[18px] tracking-[0.06em]">{activeSlot.label}</span>
            <button
              type="button"
              onClick={() => setSheetSlot(null)}
              className="ml-auto text-muted hover:text-text text-[22px] leading-none bg-transparent border-0 cursor-pointer"
              aria-label="Close"
            >
              ×
            </button>
          </div>
          <div className="px-3 py-2 border-b border-border">
            <input
              autoFocus
              placeholder="Search cards..."
              className="w-full bg-surface border border-border2 px-3 py-2 text-[14px] outline-none focus:border-green"
            />
          </div>
          <div className="flex-1 overflow-y-auto themed-scrollbar p-3">
            <CardGrid
              slot={activeSlot}
              picks={ballot.picks}
              onSelect={(n) => {
                ballot.select(activeSlot.key, n);
                setSheetSlot(null);
              }}
              minColW={150}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function MobileSubmitBar({ filled, total = SLOTS.length }: { filled: number; total?: number }) {
  const complete = filled === total;
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-bg/95 backdrop-blur border-t border-border px-3 py-2.5">
      <button
        type="button"
        className="w-full bg-green text-bg font-display tracking-[0.12em] text-[16px] py-3 flex items-center justify-center gap-2"
      >
        <DiscordIcon size={18} />
        {complete ? "LOG IN TO SUBMIT PICKS" : "LOG IN TO SAVE PICKS"}
      </button>
    </div>
  );
}

function DirLabel({ id, n, title, desc }: { id: string; n: string; title: string; desc: string }) {
  return (
    <div id={id} className="px-3 md:px-10 pt-14 pb-4 scroll-mt-20">
      <div className="flex items-baseline gap-3">
        <span className="font-display text-green text-[40px] leading-none">{n}</span>
        <span className="font-display text-[28px] tracking-[0.04em]">{title}</span>
      </div>
      <p className="text-muted text-[14px] mt-1 max-w-[760px] leading-[1.6]">{desc}</p>
    </div>
  );
}

function SlotRow({
  slot,
  card,
  active,
  onClick,
}: {
  slot: SlotDefinition;
  card: Card | undefined;
  active: boolean;
  onClick: () => void;
}) {
  const meta = SLOT_META[slot.key];
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-stretch gap-0 bg-surface border transition-colors cursor-pointer text-left group ${
        active ? "border-green" : "border-border2 hover:border-border2"
      }`}
    >
      <div className="w-1 shrink-0" style={{ background: meta.accent }} />
      <div className="flex items-center gap-3 px-3 py-2.5 flex-1 min-w-0">
        {card ? (
          <img src={card.imageArtCrop} alt="" className="w-[68px] h-[44px] object-cover border border-border2 shrink-0" />
        ) : (
          <div className="w-[68px] h-[44px] bg-surface2 border border-border2 shrink-0 flex items-center justify-center">
            <span className="text-dim text-[18px]">?</span>
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            {meta.pip}
            <span className="text-muted text-[10.5px] tracking-[0.14em] font-display">
              {slot.label.toUpperCase()}
            </span>
          </div>
          {card ? (
            <div className="flex items-center gap-1.5">
              <span className="text-text text-[14px] truncate">{card.name}</span>
              <ManaCost cost={card.manaCost} size={12} />
            </div>
          ) : (
            <span className={`text-[13px] ${active ? "text-green" : "text-dim"}`}>Select a card</span>
          )}
        </div>
        {card && (
          <span className={`text-[11px] shrink-0 ${active ? "text-green" : "text-dim group-hover:text-green"}`}>
            CHANGE
          </span>
        )}
      </div>
    </button>
  );
}

function DirectionA({ embedded = false }: { embedded?: boolean }) {
  const ballot = useMockBallot(cardsMshFixture);
  const filled = Object.keys(ballot.picks).length;
  const activeSlot = SLOTS.find((s) => s.key === ballot.activeSlot)!;
  return (
    <section>
      {!embedded && (
        <DirLabel
          id="dir-a"
          n="A"
          title="Polished rail"
          desc="Sean's two-pane bones, leveled up. Color-coded slot rail with mana pips and card art, a real progress bar, and the login CTA promoted into the hero. Lowest-risk evolution of what's there."
        />
      )}
      <div className="border border-border bg-bg mx-3 md:mx-10 px-3 md:px-10">
        <div className="flex flex-col md:flex-row md:items-center gap-4 py-5 border-b border-border">
          <div className="flex items-center gap-5 flex-1 min-w-0">
            <SetGlyph code={P0P1_SET_CODE} size={64} />
            <div className="flex-1 min-w-0">
              <SectionLabel size={12}>PACK 0, PICK 1 CHALLENGE</SectionLabel>
              <div className="flex items-baseline gap-3 mt-0.5">
                <span className="font-display tracking-[0.04em] text-[44px] leading-none">{P0P1_SET_CODE}</span>
                <span className="font-display text-[18px] text-muted tracking-[0.06em]">
                  {P0P1_SET_NAME.toUpperCase()}
                </span>
              </div>
              <div className="text-[13px] mt-1.5">
                <Countdown />
              </div>
            </div>
          </div>
          <LoginCta />
        </div>
        <div className="grid gap-6 py-5 grid-cols-1 md:grid-cols-[360px_minmax(0,1fr)]">
          <div>
            <div className="mb-3">
              <ProgressBar filled={filled} />
            </div>
            <div className="flex flex-col gap-1.5">
              {SLOTS.map((slot) => (
                <SlotRow
                  key={slot.key}
                  slot={slot}
                  card={ballot.picks[slot.key] ? cardsByName.get(ballot.picks[slot.key]!) : undefined}
                  active={ballot.activeSlot === slot.key}
                  onClick={() => ballot.setActiveSlot(slot.key)}
                />
              ))}
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-3">
              {SLOT_META[activeSlot.key].pip}
              <span className="font-display text-[20px] tracking-[0.08em]">{activeSlot.label}</span>
              <input
                placeholder="Search..."
                className="ml-auto w-40 md:w-56 bg-surface border border-border2 px-2.5 py-1.5 text-[13px] outline-none focus:border-green"
              />
            </div>
            <CardGrid slot={activeSlot} picks={ballot.picks} onSelect={(n) => ballot.select(activeSlot.key, n)} minColW={150} />
          </div>
        </div>
      </div>
    </section>
  );
}

function RosterTile({
  slot,
  card,
  active,
  onClick,
}: {
  slot: SlotDefinition;
  card: Card | undefined;
  active: boolean;
  onClick: () => void;
}) {
  const meta = SLOT_META[slot.key];
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex flex-col bg-surface border transition-colors cursor-pointer overflow-hidden w-[108px] md:w-full shrink-0 ${
        active ? "border-green" : "border-border2 hover:border-border2"
      }`}
    >
      <div className="h-1 w-full" style={{ background: meta.accent }} />
      <div className="aspect-[3/4] bg-surface2 flex items-center justify-center overflow-hidden">
        {card ? (
          <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
        ) : (
          <span className="text-dim text-[22px]">?</span>
        )}
      </div>
      <div className="px-1.5 py-1.5">
        <div className="flex items-center gap-1 mb-0.5">
          {meta.pip}
          <span className="text-muted text-[8.5px] tracking-[0.1em] font-display truncate">
            {slot.label.toUpperCase()}
          </span>
        </div>
        <div className="text-[11px] truncate text-text">{card ? card.name : "—"}</div>
      </div>
    </button>
  );
}

function DirectionB({ embedded = false }: { embedded?: boolean }) {
  const ballot = useMockBallot(cardsMshFixture);
  const filled = Object.keys(ballot.picks).length;
  const activeSlot = SLOTS.find((s) => s.key === ballot.activeSlot)!;
  return (
    <section>
      {!embedded && (
        <DirLabel
          id="dir-b"
          n="B"
          title="Roster strip"
          desc="Your standalone mockup's idea, on-brand. A persistent horizontal team strip reads as 'your hand', and the active slot's grid spans the full width below it for bigger cards. Sells the game with a fuller intro."
        />
      )}
      <div className="px-3 md:px-10">
        <div className="border border-border bg-bg p-4 md:p-6">
          <div className="flex flex-col md:flex-row md:items-start gap-5 mb-5">
            <SetGlyph code={P0P1_SET_CODE} size={72} />
            <div className="flex-1 min-w-0">
              <h1 className="font-display text-[34px] tracking-[0.03em] leading-none">PACK 0, PICK 1</h1>
              <p className="text-subtle text-[14px] mt-2 max-w-[620px] leading-[1.55]">
                Pick the strongest card for each slot before {P0P1_SET_CODE} goes live. Lock your team, then watch it
                ranked by 17Lands GIH win rate against everyone else after six weeks.
              </p>
              <div className="flex items-center flex-wrap gap-x-3 gap-y-1 mt-2.5 text-[13px]">
                <Countdown />
                <span className="text-dim">·</span>
                <span className="text-muted">Slot 9 = tiebreaker · No duplicates · Auto-saves</span>
              </div>
            </div>
            <div className="flex flex-col items-stretch md:items-end gap-3 shrink-0 w-full md:w-auto">
              <LoginCta />
              <div className="w-full md:w-56">
                <ProgressBar filled={filled} />
              </div>
            </div>
          </div>

          <div className="flex md:grid md:grid-cols-9 gap-2 overflow-x-auto md:overflow-visible pb-2 no-scrollbar border-t border-border pt-5">
            {SLOTS.map((slot) => (
              <RosterTile
                key={slot.key}
                slot={slot}
                card={ballot.picks[slot.key] ? cardsByName.get(ballot.picks[slot.key]!) : undefined}
                active={ballot.activeSlot === slot.key}
                onClick={() => ballot.setActiveSlot(slot.key)}
              />
            ))}
          </div>

          <div className="mt-5">
            <div className="flex items-center gap-2 mb-3">
              {SLOT_META[activeSlot.key].pip}
              <span className="font-display text-[18px] md:text-[22px] tracking-[0.08em]">
                Now picking: {activeSlot.label}
              </span>
              <input
                placeholder="Search..."
                className="ml-auto w-36 md:w-64 bg-surface border border-border2 px-2.5 py-1.5 text-[13px] outline-none focus:border-green"
              />
            </div>
            <CardGrid slot={activeSlot} picks={ballot.picks} onSelect={(n) => ballot.select(activeSlot.key, n)} minColW={160} />
          </div>
        </div>
      </div>
    </section>
  );
}

function TeamSlot({
  slot,
  card,
  active,
  onClick,
}: {
  slot: SlotDefinition;
  card: Card | undefined;
  active: boolean;
  onClick: () => void;
}) {
  const meta = SLOT_META[slot.key];
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative bg-surface border transition-colors cursor-pointer overflow-hidden rounded-lg ${
        active ? "border-green ring-2 ring-green/30" : "border-border2 hover:border-green/60"
      }`}
    >
      {card ? (
        <img src={card.imageNormal} alt={card.name} className="w-full block" style={{ aspectRatio: "488 / 680" }} />
      ) : (
        <div className="w-full flex flex-col items-center justify-center gap-2 text-center px-2" style={{ aspectRatio: "488 / 680" }}>
          <span className="text-[26px]">{meta.pip}</span>
          <span className="text-muted text-[11px] tracking-[0.12em] font-display leading-tight">
            {slot.label.toUpperCase()}
          </span>
          <span className="text-dim text-[10px]">Empty</span>
        </div>
      )}
      <div className="absolute top-0 left-0 right-0 h-1" style={{ background: meta.accent }} />
    </button>
  );
}

function DirectionC({ embedded = false }: { embedded?: boolean }) {
  const ballot = useMockBallot(cardsMshFixture);
  const filled = Object.keys(ballot.picks).length;
  const activeSlot = SLOTS.find((s) => s.key === ballot.activeSlot)!;
  return (
    <section>
      {!embedded && (
        <DirLabel
          id="dir-c"
          n="C"
          title="Team board"
          desc="The assembled roster is the centerpiece: nine real card slots in a deckbuilder grid, with the picker as a side panel. Maximum 'build your team' payoff, biggest departure from the current layout."
        />
      )}
      <div className="px-3 md:px-10">
        <div className="border border-border bg-bg p-4 md:p-6">
          <div className="flex flex-col md:flex-row md:items-center gap-4 mb-5">
            <SetGlyph code={P0P1_SET_CODE} size={52} />
            <div>
              <div className="flex items-baseline gap-2.5">
                <span className="font-display text-[30px] leading-none tracking-[0.03em]">{P0P1_SET_CODE}</span>
                <span className="font-display text-[15px] text-muted tracking-[0.06em]">PACK 0, PICK 1</span>
              </div>
              <div className="text-[12px] mt-1">
                <Countdown />
              </div>
            </div>
            <div className="flex items-center gap-4 md:ml-auto w-full md:w-auto">
              <div className="flex-1 md:w-48 md:flex-none">
                <ProgressBar filled={filled} />
              </div>
              <LoginCta />
            </div>
          </div>

          <div className="grid gap-6 grid-cols-1 md:grid-cols-[560px_minmax(0,1fr)]">
            <div className="self-start md:sticky md:top-24">
              <div className="flex items-center gap-2 mb-2.5">
                <SectionLabel size={11}>YOUR TEAM</SectionLabel>
                <span className="mono text-[11px] text-muted">{filled}/9</span>
              </div>
              <div className="grid grid-cols-3 gap-2.5">
                {SLOTS.map((slot) => (
                  <TeamSlot
                    key={slot.key}
                    slot={slot}
                    card={ballot.picks[slot.key] ? cardsByName.get(ballot.picks[slot.key]!) : undefined}
                    active={ballot.activeSlot === slot.key}
                    onClick={() => ballot.setActiveSlot(slot.key)}
                  />
                ))}
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-3">
                {SLOT_META[activeSlot.key].pip}
                <span className="font-display text-[20px] tracking-[0.08em]">{activeSlot.label}</span>
                <input
                  placeholder="Search..."
                  className="ml-auto w-40 md:w-56 bg-surface border border-border2 px-2.5 py-1.5 text-[13px] outline-none focus:border-green"
                />
              </div>
              <CardGrid slot={activeSlot} picks={ballot.picks} onSelect={(n) => ballot.select(activeSlot.key, n)} minColW={150} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
