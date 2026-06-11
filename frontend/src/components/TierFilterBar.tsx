import { type ReactNode } from "react";
import { cn } from "../lib/utils";
import { keyruneClass } from "./Brand";
import { Tooltip } from "./Tooltip";
import {
  MANA_VALUE_BUCKETS,
  TREND_COLOR,
  TREND_GLYPH,
  TREND_LABEL,
  type TierFilterOptions,
  type TierFilters,
} from "../data/tierList";

const RARITY_KEYRUNE: Record<string, string> = { C: "common", U: "uncommon", R: "rare", M: "mythic" };

export function TierFilterBar({
  filters,
  setFilters,
  options,
  setCode,
  stacked = false,
}: {
  filters: TierFilters;
  setFilters: (f: TierFilters) => void;
  options: TierFilterOptions;
  setCode: string;
  stacked?: boolean;
}) {
  const toggle = (key: keyof TierFilters, value: string) => {
    const arr = filters[key];
    const next = arr.includes(value) ? arr.filter((x) => x !== value) : [...arr, value];
    setFilters({ ...filters, [key]: next });
  };

  const trendState = filters.trends.length === 1 ? (filters.trends[0] as "up" | "down") : null;
  const cycleTrend = () => {
    const next = trendState === null ? ["up"] : trendState === "up" ? ["down"] : [];
    setFilters({ ...filters, trends: next });
  };
  const trendCycleLabel =
    trendState === null
      ? `${TREND_LABEL.up} (${options.trends.up})`
      : trendState === "up"
        ? `${TREND_LABEL.down} (${options.trends.down})`
        : "Show all cards";

  const rarityGroup = (
    <FilterGroup label="RARITY" stacked={stacked} joined>
      {options.rarities.map((r) => {
        const isCommon = r.value === "C";
        return (
          <IconToggle
            key={r.value}
            active={filters.rarities.includes(r.value)}
            onClick={() => toggle("rarities", r.value)}
            label={`${r.name} (${r.count})`}
            roomy
          >
            <i
              className={cn(
                "ss",
                `ss-${keyruneClass(setCode)}`,
                isCommon ? "" : `ss-${RARITY_KEYRUNE[r.value]} ss-grad`,
              )}
              style={{ fontSize: 22, color: isCommon ? "#fff" : undefined }}
            />
          </IconToggle>
        );
      })}
    </FilterGroup>
  );

  const typeGroup = (
    <FilterGroup label="TYPE" stacked={stacked} joined>
      {options.types.map((t) => (
        <IconToggle
          key={t.value}
          active={filters.cardTypes.includes(t.value)}
          onClick={() => toggle("cardTypes", t.value)}
          label={`${t.label} (${t.count})`}
          roomy
        >
          <i
            className={`ms ms-${t.ms} relative -top-[2px]`}
            style={{ fontSize: 20, WebkitTextStroke: "0.6px currentColor" }}
          />
        </IconToggle>
      ))}
    </FilterGroup>
  );

  const manaValueGroup = (
    <FilterGroup label="MANA VALUE" stacked={stacked} joined className={stacked ? undefined : "max-[1150px]:hidden"}>
      {MANA_VALUE_BUCKETS.map((mv) => (
        <IconToggle
          key={mv}
          active={filters.manaValues.includes(mv)}
          onClick={() => toggle("manaValues", mv)}
          label={`Mana value ${mv}`}
          narrow
        >
          <span className="font-display text-[18px] font-bold leading-none">{mv}</span>
        </IconToggle>
      ))}
    </FilterGroup>
  );

  const setGroup =
    options.sets.length > 1 ? (
      <FilterGroup label="SET GROUP" stacked={stacked} joined>
        {options.sets.map((s) => (
          <IconToggle
            key={s.value}
            active={filters.sets.includes(s.value)}
            onClick={() => toggle("sets", s.value)}
            label={`${s.label} (${s.count})`}
          >
            <i className={`ss ss-${keyruneClass(s.value)}`} style={{ fontSize: 19 }} />
          </IconToggle>
        ))}
      </FilterGroup>
    ) : null;

  const trendGroup = (
    <FilterGroup label="TREND" stacked={stacked} joined>
      <IconToggle active={trendState !== null} onClick={cycleTrend} label={trendCycleLabel} narrow>
        <span className="flex w-[28px] items-center justify-center">
          {trendState === null ? (
            <span className="flex gap-0.5 text-[12px] leading-none opacity-70">
              <span style={{ color: TREND_COLOR.up }}>{TREND_GLYPH.up}</span>
              <span style={{ color: TREND_COLOR.down }}>{TREND_GLYPH.down}</span>
            </span>
          ) : (
            <span className="text-[15px] leading-none" style={{ color: TREND_COLOR[trendState] }}>
              {TREND_GLYPH[trendState]}
            </span>
          )}
        </span>
      </IconToggle>
    </FilterGroup>
  );

  if (stacked) {
    return (
      <div className="flex w-full flex-col gap-y-3">
        <div className="grid w-full grid-cols-2 items-end justify-items-center gap-x-1.5">
          {rarityGroup}
          {typeGroup}
        </div>
        <div className="flex w-full flex-wrap items-end justify-between gap-x-1.5 gap-y-3">
          {manaValueGroup}
          {setGroup}
          {trendGroup}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
      {rarityGroup}
      {typeGroup}
      {manaValueGroup}
      {setGroup}
      {trendGroup}
    </div>
  );
}

const JOINED = cn(
  "[&>button]:rounded-none",
  "[&>button:first-child]:rounded-l-md [&>button:last-child]:rounded-r-md",
  "[&>button:not(:first-child)]:-ml-px",
);

function FilterGroup({
  label,
  children,
  stacked,
  joined = false,
  className,
}: {
  label: string;
  children: ReactNode;
  stacked: boolean;
  joined?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col", stacked ? "items-center gap-1" : "gap-0.5", className)}>
      <span className="font-display text-[13px] tracking-[0.2em] text-muted">{label}</span>
      <div className={cn("flex", joined ? JOINED : "gap-1.5")}>{children}</div>
    </div>
  );
}

function IconToggle({
  active,
  onClick,
  label,
  children,
  roomy = false,
  narrow = false,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  children: ReactNode;
  roomy?: boolean;
  narrow?: boolean;
}) {
  return (
    <Tooltip label={label}>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "relative flex h-10 items-center justify-center rounded border transition-colors",
          roomy ? "min-w-[40px] px-2.5" : narrow ? "min-w-[34px] px-1.5" : "min-w-[40px] px-2",
          active
            ? "z-10 border-green bg-green/10 text-text"
            : "border-border2 bg-transparent text-muted hover:bg-surface hover:text-text",
        )}
      >
        {children}
      </button>
    </Tooltip>
  );
}
