import { BsAsterisk, BsPaletteFill } from "react-icons/bs";

import { Pip } from "./ManaPips";
import { cn } from "../lib/utils";
import { MULTI, OTHER, colorsDisplayName } from "../data/filters";

export function ColorsSwitcher({
  activeCode,
  onChange,
  chips,
  includeAll = true,
  variant = "desktop",
}: {
  activeCode: string;
  onChange: (code: string) => void;
  chips: string[];
  includeAll?: boolean;
  variant?: "desktop" | "mobile";
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
          onClick={() => onChange(code)}
          pipSize={isMobile ? 12 : 12}
        />
      ))}
    </div>
  );
}

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
          "shrink-0 h-[26px] px-2.5 border inline-flex items-center gap-1.5 cursor-pointer transition-colors font-display tracking-[0.18em] text-[11px]",
          activeAccent && "border-green bg-green/10 text-green",
          activeAll && "border-border2 bg-surface text-text",
          !active && "border-border2 bg-transparent text-muted hover:bg-surface",
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
        active ? "border-green bg-green/10" : "border-border2 bg-transparent hover:bg-surface",
      )}
      aria-label={code}
    >
      {[...code].map((c) => (
        <Pip key={c} c={c as "W" | "U" | "B" | "R" | "G"} size={pipSize} />
      ))}
    </button>
  );
}

