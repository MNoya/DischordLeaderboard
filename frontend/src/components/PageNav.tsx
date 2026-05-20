import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "./Icons";
import { cn } from "../lib/utils";
import { ALogo } from "./Brand";

type To = string | { pathname: string; search?: string };

const baseLinkCls =
  "bg-transparent border-none font-display text-[12px] leading-none flex items-center transition-colors";
const disabledCls = "opacity-30 cursor-default pointer-events-none";

export function BackButton({
  to,
  onClick,
  label = "BACK TO LEADERBOARD",
  compact = false,
  inline = false,
}: {
  to?: To;
  onClick?: () => void;
  label?: string;
  compact?: boolean;
  inline?: boolean;
}) {
  const cls = cn(
    baseLinkCls,
    "text-muted cursor-pointer hover:text-text no-underline",
    compact ? "tracking-[0.15em] gap-1.5" : "tracking-[0.18em] gap-1",
    !compact && !inline && "mb-3.5",
  );
  const content = (
    <>
      <ChevronLeft size={14} className="shrink-0" />
      {compact ? "BACK" : label}
    </>
  );
  if (to) {
    return (
      <Link to={to} className={cls}>
        {content}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className={cls}>
      {content}
    </button>
  );
}

export function PrevNextNav({
  prevTo,
  nextTo,
  prevLabel = "PREV",
  nextLabel = "NEXT",
  prevAriaLabel,
  nextAriaLabel,
  compact = false,
}: {
  prevTo: To | null;
  nextTo: To | null;
  prevLabel?: string;
  nextLabel?: string;
  prevAriaLabel?: string;
  nextAriaLabel?: string;
  compact?: boolean;
}) {
  const cls = cn(
    baseLinkCls,
    "tracking-[0.15em] gap-1.5 text-muted",
    "cursor-pointer hover:text-text no-underline",
  );
  return (
    <div className={cn("flex items-center", compact ? "gap-2" : "gap-3")}>
      {prevTo ? (
        <Link to={prevTo} className={cls} aria-label={prevAriaLabel ?? "Previous"}>
          <ChevronLeft size={14} className="shrink-0" /> {prevLabel}
        </Link>
      ) : (
        <span className={cn(cls, disabledCls)} aria-disabled="true">
          <ChevronLeft size={14} className="shrink-0" /> {prevLabel}
        </span>
      )}
      <span className="text-dim text-[12px]">·</span>
      {nextTo ? (
        <Link to={nextTo} className={cls} aria-label={nextAriaLabel ?? "Next"}>
          {nextLabel} <ChevronRight size={14} className="shrink-0" />
        </Link>
      ) : (
        <span className={cn(cls, disabledCls)} aria-disabled="true">
          {nextLabel} <ChevronRight size={14} className="shrink-0" />
        </span>
      )}
    </div>
  );
}

export function MobilePageHeader({
  backTo,
  backOnClick,
  prevTo,
  nextTo,
  prevAriaLabel,
  nextAriaLabel,
}: {
  backTo?: To;
  backOnClick?: () => void;
  prevTo: To | null;
  nextTo: To | null;
  prevAriaLabel?: string;
  nextAriaLabel?: string;
}) {
  return (
    <header className="py-3 px-[18px] border-b border-border grid grid-cols-3 items-center">
      <BackButton to={backTo} onClick={backOnClick} compact inline />
      <Link to="/" className="flex justify-center no-underline" aria-label="Home">
        <div className="flex items-center overflow-visible" style={{ height: 14 }}>
          <ALogo size={22} />
        </div>
      </Link>
      <div className="justify-self-end">
        <PrevNextNav
          prevTo={prevTo}
          nextTo={nextTo}
          prevAriaLabel={prevAriaLabel}
          nextAriaLabel={nextAriaLabel}
          compact
        />
      </div>
    </header>
  );
}
