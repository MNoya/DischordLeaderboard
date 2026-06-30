import { type MouseEvent } from "react";
import {
  VsCardShell,
  VsCategoryHeader,
  VsTwoColumnLayout,
  VsThreeColumnLayout,
  VsMetricSide,
  PagerNav,
  useVersusPager,
  VersusModal,
} from "./PickVersusCard";
import type { MidwaySlotVersus, MidwayVersusSide } from "../../data/p0p1Results";
import type { SlotKey } from "../../types/p0p1";

const GREEN = "#2ee85c";
const GOLD = "#ffc63a";
const TEXT = "#e6ecf5";

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
}

const ROLE_LABEL: Record<Role, string> = {
  yours: "YOUR PICK",
  crowd: "CROWD PICK",
  best: "BEST PICK",
};

// Keys are role names sorted alphabetically so the lookup is order-independent
const MERGED_LABEL: Record<string, string> = {
  "crowd+yours": "CROWD/YOUR PICK",
  "best+yours": "BEST PICK",
  "best+crowd": "BEST PICK",
  "best+crowd+yours": "BEST PICK",
};

function accentFor(roles: Role[]): string {
  if (roles.includes("best")) return GOLD;
  if (roles.includes("crowd")) return GREEN;
  return TEXT;
}

function buildColumns(versus: MidwaySlotVersus): Column[] {
  const present: Array<{ role: Role; side: MidwayVersusSide }> = [];
  present.push({ role: "crowd", side: versus.crowd });
  present.push({ role: "best", side: versus.best });
  if (versus.yours) present.push({ role: "yours", side: versus.yours });

  const order: string[] = [];
  const grouped = new Map<string, { roles: Role[]; side: MidwayVersusSide }>();
  for (const { role, side } of present) {
    if (!grouped.has(side.name)) {
      order.push(side.name);
      grouped.set(side.name, { roles: [], side });
    }
    grouped.get(side.name)!.roles.push(role);
  }

  // Ensure the column containing "yours" is always rightmost
  if (versus.yours) {
    const idx = order.indexOf(versus.yours.name);
    if (idx !== -1) {
      order.splice(idx, 1);
      order.push(versus.yours.name);
    }
  }

  return order.map((name) => {
    const { roles, side } = grouped.get(name)!;
    const key = [...roles].sort().join("+");
    const label = MERGED_LABEL[key] ?? ROLE_LABEL[roles[0]];
    const accent = accentFor(roles);
    return { side, roles, label, accent };
  });
}

// ── Pager hook ─────────────────────────────────────────────────────────────────

export function useMidwayVersusPager(list: MidwaySlotVersus[]) {
  return useVersusPager(list);
}

// ── Modal ──────────────────────────────────────────────────────────────────────

export function MidwayVersusModal({
  pager,
}: {
  pager: ReturnType<typeof useMidwayVersusPager>;
}) {
  return (
    <VersusModal
      pager={pager}
      padding="p-4"
      renderCard={(versus, nav) => <MidwayVersusCard versus={versus} {...nav} />}
    />
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

function columnCaption(column: Column): string {
  return `GIH`;
}

function SoloLayout({ column }: { column: Column }) {
  return (
    <VsMetricSide
      label={column.label}
      labelColor={column.accent}
      value={gihwrDisplay(column.side.gihwr)}
      valueColor={column.accent}
      caption={columnCaption(column)}
      fillPct={barFill(column.side.gihwr)}
      barColor={column.accent}
      dim={column.side.gihwr === null}
      density="comfortable"
      solo
      imageUrl={column.side.imageUrl}
      name={column.side.name}
    />
  );
}

function TwoColumnLayout({ columns }: { columns: [Column, Column] }) {
  return (
    <VsTwoColumnLayout
      left={<GihwrSide column={columns[0]} />}
      right={<GihwrSide column={columns[1]} />}
    />
  );
}

function ThreeColumnLayout({ columns }: { columns: [Column, Column, Column] }) {
  return (
    <VsThreeColumnLayout
      left={<GihwrCompact column={columns[0]} />}
      middle={<GihwrCompact column={columns[1]} />}
      right={<GihwrCompact column={columns[2]} />}
    />
  );
}

function GihwrSide({ column }: { column: Column }) {
  return (
    <VsMetricSide
      label={column.label}
      labelColor={column.accent}
      value={gihwrDisplay(column.side.gihwr)}
      valueColor={column.accent}
      caption={columnCaption(column)}
      fillPct={barFill(column.side.gihwr)}
      barColor={column.accent}
      dim={column.side.gihwr === null}
      density="comfortable"
      imageUrl={column.side.imageUrl}
      name={column.side.name}
    />
  );
}

function GihwrCompact({ column }: { column: Column }) {
  return (
    <VsMetricSide
      label={column.label}
      labelColor={column.accent}
      value={gihwrDisplay(column.side.gihwr)}
      valueColor={column.accent}
      caption={columnCaption(column)}
      fillPct={barFill(column.side.gihwr)}
      barColor={column.accent}
      dim={column.side.gihwr === null}
      density="compact"
      imageUrl={column.side.imageUrl}
      name={column.side.name}
    />
  );
}
