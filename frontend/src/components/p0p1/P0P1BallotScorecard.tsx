import type { ReactNode } from "react";
import { HelpCircle } from "lucide-react";
import { Tooltip } from "../Tooltip";
import { groupBySlot, findExtremes, classifyYourPick } from "../../data/p0p1Stats";
import { SLOTS } from "../../data/p0p1Slots";
import type { P0P1PickStat } from "../../types/p0p1";

type PickState = "fav" | "pack" | "rogue";
type ScoredPick = { state: PickState; cardName: string; pickCount: number };

export const CHAMFER = "polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)";
const CELL_ORDER: Record<PickState, number> = { fav: 0, pack: 1, rogue: 2 };
const CAT_COLOR: Record<PickState, string> = {
  fav: "#2ee85c",
  pack: "#4aa8ff",
  rogue: "#a98eff",
};

export function P0P1BallotScorecard({
  pickStats,
  picksBySlot,
}: {
  pickStats: P0P1PickStat[];
  picksBySlot: Map<string, string>;
}) {
  const picks = ballotPicks(pickStats, picksBySlot);
  if (picks.length === 0) {
    return null;
  }
  const favs = picks.filter((p) => p.state === "fav").length;
  const mids = picks.filter((p) => p.state === "pack").length;
  const rogues = picks.filter((p) => p.state === "rogue");
  const boldest = boldestRogue(rogues);
  const sorted = [...picks].sort((a, b) => CELL_ORDER[a.state] - CELL_ORDER[b.state]);

  return (
    <div className="inline-block animate-fadeUpIn" style={{ clipPath: CHAMFER, background: "#3b4458", padding: 1 }}>
      <div className="bg-surface2 w-[clamp(280px,22vw,340px)] px-5 py-2.5 flex flex-col gap-2" style={{ clipPath: CHAMFER }}>
        <Tooltip label={<BallotLegend />} side="bottom" align="start" hideArrow className="max-w-[320px]">
          <button
            type="button"
            className="group inline-flex items-center gap-1.5 self-start cursor-help bg-transparent border-0 p-0"
          >
            <HelpCircle size={15} strokeWidth={2} className="text-white transition-colors" />
            <span className="font-display text-white" style={{ fontSize: 15, letterSpacing: "0.22em" }}>YOUR BALLOT</span>
          </button>
        </Tooltip>

        <div className="flex items-center justify-between">
          <StatInline n={favs} label="CROWD" color={CAT_COLOR.fav} />
          <StatInline n={mids} label="SPLIT" color={CAT_COLOR.pack} />
          <StatInline n={rogues.length} label="ROGUE" color={CAT_COLOR.rogue} className="mr-[5px]" />
        </div>

        <div className="flex gap-1 -ml-[5px]" aria-hidden>
          {sorted.map((pick, i) => (
            <div key={i} className="h-2.5 flex-1 rounded-[1px]" style={{ background: CAT_COLOR[pick.state] }} />
          ))}
        </div>

        {boldest && (
          <p className="font-body text-subtle text-[12px] leading-snug -ml-[10px]">
            <span className="mr-1">🌶️</span>
            {rarityPrefix(boldest.pickCount)}{" "}
            <span className="text-text">{boldest.cardName}</span>
          </p>
        )}
      </div>
    </div>
  );
}

function StatInline({ n, label, color, className }: { n: number; label: string; color: string; className?: string }) {
  return (
    <span className={`flex items-baseline gap-1.5 ${className ?? ""}`}>
      <span className="font-display leading-none" style={{ fontSize: 24, color }}>{n}</span>
      <span className="font-body text-[12px] leading-none" style={{ color }}>{label}</span>
    </span>
  );
}

function BallotLegend() {
  return (
    <div className="flex flex-col gap-1.5 text-left">
      <LegendRow color={CAT_COLOR.fav} term="Crowd" def={<>you picked the <b className="font-semibold text-text">most popular</b> card</>} />
      <LegendRow color={CAT_COLOR.pack} term="Split" def={<>you picked a card in the <b className="font-semibold text-text">middle</b> of the pack</>} />
      <LegendRow color={CAT_COLOR.rogue} term="Rogue" def={<>you picked one of the <b className="font-semibold text-text">least popular</b> cards</>} />
    </div>
  );
}

function LegendRow({ color, term, def }: { color: string; term: string; def: ReactNode }) {
  return (
    <div className="leading-snug">
      <span className="font-semibold" style={{ color }}>{term}</span> <span className="text-subtle">- {def}</span>
    </div>
  );
}

function ballotPicks(pickStats: P0P1PickStat[], picksBySlot: Map<string, string>): ScoredPick[] {
  const grouped = groupBySlot(pickStats);
  const picks: ScoredPick[] = [];
  for (const slot of SLOTS) {
    const cardName = picksBySlot.get(slot.key);
    if (!cardName) {
      continue;
    }
    const slotStats = grouped.get(slot.key);
    const yourStat = slotStats?.find((s) => s.cardName === cardName);
    if (!slotStats || !yourStat) {
      continue;
    }
    const { most, least } = findExtremes(slotStats);
    const state = classifyYourPick(yourStat, most, least).state;
    picks.push({
      state: state === "most" ? "fav" : state === "rogue" ? "rogue" : "pack",
      cardName,
      pickCount: yourStat.pickCount,
    });
  }
  return picks;
}

function boldestRogue(rogues: ScoredPick[]): ScoredPick | null {
  let boldest: ScoredPick | null = null;
  for (const rogue of rogues) {
    if (!boldest || rogue.pickCount < boldest.pickCount) {
      boldest = rogue;
    }
  }
  return boldest;
}

function rarityPrefix(pickCount: number): string {
  const others = pickCount - 1;
  if (others <= 0) {
    return "You were the only one to pick";
  }
  if (others === 1) {
    return "Only you and 1 other picked";
  }
  return `Only you and ${others} others picked`;
}
