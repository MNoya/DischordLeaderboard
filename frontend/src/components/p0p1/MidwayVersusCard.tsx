import { useEffect, useState, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { VsCardShell, VsCategoryHeader, VsColumnDivider, PagerNav } from "./PickVersusCard";
import type { MidwaySlotVersus, MidwayVersusSide } from "../../data/p0p1Results";
import type { SlotKey } from "../../types/p0p1";

const SUBTLE = "#9aa3b5";
const TEXT = "#e6ecf5";
const GREEN = "#2ee85c";
const MUTED = "#7a8395";

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

function accentFor(roles: Role[]): { accent: string; numColor: string } {
  if (roles.includes("best")) return { accent: GREEN, numColor: GREEN };
  if (roles.includes("crowd")) return { accent: SUBTLE, numColor: SUBTLE };
  return { accent: TEXT, numColor: TEXT };
}

function buildColumns(versus: MidwaySlotVersus): Column[] {
  const present: Array<{ role: Role; side: MidwayVersusSide }> = [];
  if (versus.yours) present.push({ role: "yours", side: versus.yours });
  present.push({ role: "crowd", side: versus.crowd });
  present.push({ role: "best", side: versus.best });

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
    const { accent, numColor } = accentFor(roles);
    return { side, roles, label, accent, numColor };
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
  const maxWidth = columns.length === 1 ? 420 : columns.length === 2 ? 640 : 820;

  return (
    <VsCardShell maxWidth={maxWidth} onClick={stop}>
      <div className="overflow-y-auto flex-1 min-h-0 px-2 pt-2 lg:px-4">
        <VsCategoryHeader slotKey={versus.slotKey as SlotKey} slotLabel={versus.slotLabel} />
        {columns.length === 1 ? (
          <SoloLayout column={columns[0]} />
        ) : columns.length === 2 ? (
          <TwoColumnLayout columns={columns as [Column, Column]} />
        ) : (
          <ThreeColumnLayout columns={columns as [Column, Column, Column]} />
        )}
      </div>
      <PagerNav onPrev={onPrev} onNext={onNext} paged={paged} prevLabel="Prev Slot" nextLabel="Next Slot" />
    </VsCardShell>
  );
}

// ── Layout variants ────────────────────────────────────────────────────────────

function SoloLayout({ column }: { column: Column }) {
  return (
    <div className="flex flex-col gap-2 pb-2">
      <GihwrMeta column={column} size="lg" />
      <GihwrBar column={column} />
      <CardImage column={column} className="mx-auto max-h-[58vh] w-auto rounded-[10px] max-w-[200px] lg:max-w-full" />
    </div>
  );
}

function TwoColumnLayout({ columns }: { columns: [Column, Column] }) {
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] gap-2 lg:gap-5 pb-2">
      <GihwrSide column={columns[0]} />
      <VsColumnDivider />
      <GihwrSide column={columns[1]} />
    </div>
  );
}

function ThreeColumnLayout({ columns }: { columns: [Column, Column, Column] }) {
  return (
    <div className="grid gap-0 pb-2" style={{ gridTemplateColumns: "1fr auto 1fr auto 1fr" }}>
      <CompactColumn column={columns[0]} />
      <VsColumnDivider />
      <CompactColumn column={columns[1]} />
      <VsColumnDivider />
      <CompactColumn column={columns[2]} />
    </div>
  );
}

// ── Side renderers ─────────────────────────────────────────────────────────────

// 2-col and solo: tall layout matching PickVersusCard's VersusSide
function GihwrSide({ column }: { column: Column }) {
  return (
    <div className="flex min-w-0 flex-col gap-2.5 lg:gap-3">
      <div className="flex flex-col gap-2 px-1">
        <GihwrMeta column={column} size="lg" />
        <GihwrBar column={column} />
      </div>
      <CardImage column={column} className="mx-auto max-h-[58vh] w-auto rounded-[10px] max-w-full" />
    </div>
  );
}

// 3-col compact: full-card natural width, condensed metadata
function CompactColumn({ column }: { column: Column }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5 px-1 pb-1">
      <GihwrMeta column={column} size="sm" />
      <GihwrBar column={column} />
      <CardImage column={column} className="w-full rounded-[5px]" />
      <span className="truncate text-center font-body text-[9px] leading-snug" style={{ color: MUTED }}>
        {column.side.name || "—"}
      </span>
    </div>
  );
}

// ── Primitives ─────────────────────────────────────────────────────────────────

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
        className="font-mono tabular-nums font-semibold leading-none"
        style={{ fontSize: size === "lg" ? 30 : 20, color: dim ? "#4a5568" : column.numColor }}
      >
        {gihwrDisplay(column.side.gihwr)}
      </span>
    </div>
  );
}

function GihwrBar({ column }: { column: Column }) {
  const fill = barFill(column.side.gihwr);
  return (
    <div className="h-2 overflow-hidden rounded-full bg-white/10">
      <div className="h-full rounded-full" style={{ width: `${fill}%`, background: column.accent }} />
    </div>
  );
}

function CardImage({ column, className }: { column: Column; className: string }) {
  return column.side.imageUrl ? (
    <img src={column.side.imageUrl} alt={column.side.name} className={className} />
  ) : (
    <div className={`rounded-[10px] bg-white/5 ${className}`} style={{ aspectRatio: "488/680" }} />
  );
}

