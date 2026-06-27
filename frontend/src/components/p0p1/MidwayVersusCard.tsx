import { useEffect, useState, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { ModalNavButton } from "../ModalNavButton";
import { SlotPip } from "./slotVisuals";
import type { MidwaySlotVersus, MidwayVersusSide } from "../../data/p0p1Results";
import type { SlotKey } from "../../types/p0p1";

const MAT = "#161b26";
const MUTED = "#6b7585";
const SUBTLE = "#9aa3b5";
const TEXT = "#e6ecf5";
const GREEN = "#2ee85c";

const BAR_MIN = 0.45;
const BAR_MAX = 0.70;

function barFill(gihwr: number | null): number {
  if (gihwr === null) return 0;
  return Math.max(4, Math.min(100, ((gihwr - BAR_MIN) / (BAR_MAX - BAR_MIN)) * 100));
}

function gihwrDisplay(gihwr: number | null): string {
  return gihwr !== null ? `${(gihwr * 100).toFixed(1)}%` : "—";
}

// ── Column collapse ────────────────────────────────────────────────────────────

type Role = "yours" | "crowd" | "best";

interface Column {
  side: MidwayVersusSide;
  roles: Role[];
  label: string;
  accent: string;
  numColor: string;
  barFill: string; // CSS bg class or value
}

const ROLE_LABEL: Record<Role, string> = {
  yours: "YOUR PICK",
  crowd: "CROWD TEAM",
  best: "BEST POSSIBLE",
};

const MERGED_LABEL: Record<string, string> = {
  "yours+crowd": "YOU + CROWD",
  "yours+best": "YOU + BEST",
  "crowd+best": "CROWD + BEST",
  "yours+crowd+best": "ALL AGREE",
};

function accentFor(roles: Role[]): { accent: string; numColor: string; barFill: string } {
  if (roles.includes("best")) return { accent: GREEN, numColor: GREEN, barFill: "bg-[#2ee85c]" };
  if (roles.includes("crowd")) return { accent: SUBTLE, numColor: SUBTLE, barFill: "bg-[#9aa3b5]/45" };
  return { accent: TEXT, numColor: TEXT, barFill: "bg-white/50" };
}

function buildColumns(versus: MidwaySlotVersus): Column[] {
  const present: Array<{ role: Role; side: MidwayVersusSide }> = [];
  if (versus.yours) present.push({ role: "yours", side: versus.yours });
  present.push({ role: "crowd", side: versus.crowd });
  present.push({ role: "best", side: versus.best });

  // Group by card name; maintain first-seen order
  const order: string[] = [];
  const grouped = new Map<string, { roles: Role[]; side: MidwayVersusSide }>();
  for (const { role, side } of present) {
    if (!grouped.has(side.name)) {
      order.push(side.name);
      grouped.set(side.name, { roles: [], side });
    }
    grouped.get(side.name)!.roles.push(role);
  }

  return order.map((name) => {
    const { roles, side } = grouped.get(name)!;
    const key = roles.join("+");
    const label = MERGED_LABEL[key] ?? ROLE_LABEL[roles[0]];
    const { accent, numColor, barFill: barClass } = accentFor(roles);
    return { side, roles, label, accent, numColor, barFill: barClass };
  });
}

// ── Pager hook ─────────────────────────────────────────────────────────────────

export function useMidwayVersusPager(list: MidwaySlotVersus[]) {
  const [index, setIndex] = useState<number | null>(null);
  const current = index === null ? null : list[index] ?? null;
  return {
    list,
    index,
    current,
    open: (i: number) => setIndex(i),
    close: () => setIndex(null),
    step: (delta: number) =>
      setIndex((cur) => (cur === null ? cur : (cur + delta + list.length) % list.length)),
  };
}

// ── Modal ──────────────────────────────────────────────────────────────────────

export function MidwayVersusModal({
  pager,
}: {
  pager: ReturnType<typeof useMidwayVersusPager>;
}) {
  const { current, index, list, close, step } = pager;

  useEffect(() => {
    if (current === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === "ArrowRight") step(1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [current, close, step]);

  if (current === null || index === null) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-4"
      onClick={close}
    >
      <MidwayVersusCard
        versus={current}
        paged={list.length > 1}
        onPrev={() => step(-1)}
        onNext={() => step(1)}
      />
    </div>,
    document.body,
  );
}

// ── Card ───────────────────────────────────────────────────────────────────────

export function MidwayVersusCard({
  versus,
  onPrev,
  onNext,
  paged = false,
}: {
  versus: MidwaySlotVersus;
  onPrev?: () => void;
  onNext?: () => void;
  paged?: boolean;
}) {
  const stop = (e: MouseEvent) => e.stopPropagation();
  const columns = buildColumns(versus);

  return (
    <div
      onClick={stop}
      className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-xl border border-white/15 shadow-2xl"
      style={{
        backgroundColor: MAT,
        maxWidth: columns.length === 1 ? 420 : columns.length === 2 ? 640 : 820,
      }}
    >
      {/* Slot header */}
      <div className="flex items-center justify-center gap-2 px-4 pb-3 pt-3 shrink-0">
        <SlotPip slotKey={versus.slotKey as SlotKey} size={16} />
        <span
          className="font-display leading-none tracking-[0.18em]"
          style={{ fontSize: 18, color: TEXT }}
        >
          {versus.slotLabel.toUpperCase()}
        </span>
      </div>

      {/* Columns */}
      <div className="overflow-y-auto px-2 pb-1">
        {columns.length === 1 ? (
          <SoloLayout column={columns[0]} />
        ) : columns.length === 2 ? (
          <TwoColumnLayout columns={columns as [Column, Column]} />
        ) : (
          <ThreeColumnLayout columns={columns as [Column, Column, Column]} />
        )}
      </div>

      {/* Pager */}
      {paged && (
        <div className="flex items-center justify-between px-3 py-3 shrink-0 border-t border-white/8">
          <ModalNavButton dir="prev" label="Prev Slot" onClick={onPrev} />
          <ModalNavButton dir="next" label="Next Slot" onClick={onNext} />
        </div>
      )}
    </div>
  );
}

// ── Layout variants ────────────────────────────────────────────────────────────

function SoloLayout({ column }: { column: Column }) {
  return (
    <div className="px-2 pb-2 flex flex-col gap-2">
      <GihwrMeta column={column} size="lg" />
      <FillBar column={column} />
      <CardImage column={column} className="mx-auto max-h-[58vh] w-auto rounded-[10px]" />
    </div>
  );
}

function TwoColumnLayout({ columns }: { columns: [Column, Column] }) {
  return (
    <div className="grid gap-0" style={{ gridTemplateColumns: "1fr auto 1fr" }}>
      <SideColumn column={columns[0]} />
      <VsDivider />
      <SideColumn column={columns[1]} />
    </div>
  );
}

function ThreeColumnLayout({ columns }: { columns: [Column, Column, Column] }) {
  return (
    <div className="grid gap-0" style={{ gridTemplateColumns: "1fr auto 1fr auto 1fr" }}>
      <CompactColumn column={columns[0]} />
      <VsDivider />
      <CompactColumn column={columns[1]} />
      <VsDivider />
      <CompactColumn column={columns[2]} />
    </div>
  );
}

// ── Shared primitives ──────────────────────────────────────────────────────────

function VsDivider() {
  return (
    <div className="relative flex w-8 flex-col items-center self-stretch lg:w-10">
      <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-white/10" />
      <div
        className="relative z-10 mt-1 flex h-7 w-7 items-center justify-center rounded-full border border-white/35 font-display text-[10px] tracking-[0.06em] lg:h-8 lg:w-8 lg:text-[11px]"
        style={{ backgroundColor: MAT, color: MUTED }}
      >
        VS
      </div>
    </div>
  );
}

function GihwrMeta({ column, size }: { column: Column; size: "sm" | "lg" }) {
  const dim = column.side.gihwr === null;
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className="font-display leading-none tracking-[0.14em]"
        style={{ fontSize: size === "lg" ? 13 : 10, color: column.accent }}
      >
        {column.label}
      </span>
      <span
        className="font-mono tabular-nums font-bold leading-none"
        style={{
          fontSize: size === "lg" ? 30 : 20,
          color: dim ? "#4a5568" : column.numColor,
        }}
      >
        {gihwrDisplay(column.side.gihwr)}
      </span>
      <span className="font-mono leading-none" style={{ fontSize: size === "lg" ? 11 : 8, color: MUTED }}>
        {column.side.gih.toLocaleString()} games
        {column.side.gihwr === null ? " · below floor" : ""}
      </span>
    </div>
  );
}

function FillBar({ column }: { column: Column }) {
  const fill = barFill(column.side.gihwr);
  return (
    <div className="h-[3px] overflow-hidden rounded-full bg-white/8">
      <div className={`h-full rounded-full ${column.barFill}`} style={{ width: `${fill}%` }} />
    </div>
  );
}

function CardImage({ column, className }: { column: Column; className: string }) {
  return column.side.imageUrl ? (
    <img src={column.side.imageUrl} alt={column.side.name} className={className} />
  ) : (
    <div className={`bg-white/5 rounded-[10px] ${className}`} style={{ aspectRatio: "488/680" }} />
  );
}

// 2-column side: tall layout matching PickVersusCard
function SideColumn({ column }: { column: Column }) {
  return (
    <div className="flex min-w-0 flex-col gap-2 px-2 pb-2 lg:gap-3 lg:px-4">
      <div className="flex flex-col gap-1 pt-1">
        <GihwrMeta column={column} size="lg" />
        <FillBar column={column} />
      </div>
      <CardImage column={column} className="mx-auto max-h-[58vh] w-auto rounded-[10px] max-w-full" />
    </div>
  );
}

// 3-column compact: natural full-card width, no height cap
function CompactColumn({ column }: { column: Column }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5 px-1.5 pb-2">
      <GihwrMeta column={column} size="sm" />
      <FillBar column={column} />
      <CardImage column={column} className="w-full rounded-[5px]" />
      <span className="truncate text-center font-body text-[9px] leading-snug" style={{ color: SUBTLE }}>
        {column.side.name || "—"}
      </span>
    </div>
  );
}
