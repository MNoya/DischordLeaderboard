import { BsAsterisk, BsPaletteFill } from "./Icons";

import { Pip } from "./ManaPips";
import { cn } from "../lib/utils";
import { MULTI, OTHER, colorsDisplayName } from "../data/filters";
import { TOGGLE_ACTIVE, TOGGLE_INACTIVE } from "../lib/toggle-styles";

export function ColorsSwitcher({
  activeCode,
  onChange,
  chips,
  includeAll = true,
  variant = "desktop",
  loading = false,
}: {
  activeCode: string;
  onChange: (code: string) => void;
  chips: string[];
  includeAll?: boolean;
  variant?: "desktop" | "mobile";
  loading?: boolean;
}) {
  const codes: string[] = includeAll ? ["ALL", ...chips] : chips;
  const isMobile = variant === "mobile";
  return (
    <div
      className={cn(
        "flex items-center gap-1 flex-wrap min-w-0",
        isMobile && "flex-nowrap overflow-x-auto no-scrollbar pb-2 -mb-2 w-full",
      )}
    >
      {codes.map((code) => (
        <Chip
          key={code}
          code={code}
          active={code === activeCode}
          onClick={() => onChange(code === activeCode && code !== "ALL" ? "ALL" : code)}
          pipSize={isMobile ? 12 : 12}
        />
      ))}
      {loading && chips.length === 0 && SKELETON_CHIP_WIDTHS.map((w, i) => (
        <span
          key={i}
          className="shrink-0 h-[26px] border border-border2 bg-surface2/40 animate-pulse"
          style={{ width: w }}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

const SKELETON_CHIP_WIDTHS = [44, 60, 60, 44, 44, 60, 44, 52];

function Chip({
  code,
  active,
  onClick,
  pipSize,
}: {
  code: string;
  active: boolean;
  onClick: () => void;
  pipSize: number;
}) {
  if (code === "ALL" || code === MULTI || code === OTHER) {
    const label = code === "ALL" ? "ALL" : colorsDisplayName(code);
    const activeAll = active && code === "ALL";
    const activeAccent = active && code !== "ALL";
    return (
      <button
        onClick={onClick}
        className={cn(
          "shrink-0 h-[26px] px-2.5 border inline-flex items-center gap-1.5 cursor-pointer transition-colors font-display tracking-[0.18em] text-[13px]",
          activeAccent && TOGGLE_ACTIVE,
          activeAll && "border-border2 bg-surface text-text",
          !active && TOGGLE_INACTIVE,
        )}
      >
        {code === MULTI && <BsPaletteFill size={pipSize} aria-hidden="true" />}
        {code === OTHER && <BsAsterisk size={pipSize - 1} aria-hidden="true" />}
        {label}
      </button>
    );
  }
  return (
    <button
      onClick={onClick}
      className={cn(
        "shrink-0 h-[26px] px-[7px] border inline-flex items-center gap-0.5 cursor-pointer transition-colors",
        active ? TOGGLE_ACTIVE : TOGGLE_INACTIVE,
      )}
      aria-label={code}
    >
      {[...code].map((c) => (
        <Pip key={c} c={c as "W" | "U" | "B" | "R" | "G"} size={pipSize} />
      ))}
    </button>
  );
}

