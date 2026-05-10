import type { FilterOption } from "./filters";

// Single source of truth for per-format swatch colors. Keep the keys aligned
// with the backend `format_label` groups so dropdowns, donuts, and legend
// chips all read from the same palette.
export const FMT_COLORS: Record<string, string> = {
  Premier: "#2ee85c",
  Trad: "#5c8aff",
  Quick: "#ffc63a",
  Sealed: "#ff5d8c",
  LCQ: "#ff7700",
};

export const FMT_DEFAULT_COLOR = "#5c8aff";

const FORMAT_SHORT: Record<string, string> = {
  PremierDraft: "PREMIER",
  TradDraft: "TRAD",
  QuickDraft: "QUICK",
  Sealed: "SEALED",
  TradSealed: "TRAD SEALED",
  ArenaDirect_Sealed: "ARENA DIR",
  QualifierPlayInSealed: "QUAL PLAY-IN",
  PickTwoDraft: "PICK 2",
  Emblem_QuickDraft: "QUICK",
  LimitedChampionshipQualifier_Draft1: "LCQ 1",
  LimitedChampionshipQualifier_Draft2: "LCQ 2",
  Premier: "PREMIER",
  Trad: "TRAD",
  Quick: "QUICK",
  LCQ: "LCQ",
  "Trad Sealed": "TRAD SEALED",
  "Arena Direct": "ARENA DIR",
};

export function shortFormat(format: string): string {
  return FORMAT_SHORT[format] ?? format.replace(/_/g, " ").toUpperCase();
}

// Dropdown row + selected-value renderer used by every FilterDropdown that
// drives a format filter. Reads the swatch color from FMT_COLORS so the
// option chips always match the donut palette.
export const renderFormatOption = (opt: FilterOption) => {
  if (opt.value === "ALL") return <span>{opt.label}</span>;
  const color = FMT_COLORS[opt.value] ?? FMT_DEFAULT_COLOR;
  return (
    <span className="flex items-center gap-2">
      <span className="w-2 h-2 inline-block shrink-0" style={{ background: color }} />
      <span>{opt.label}</span>
    </span>
  );
};
