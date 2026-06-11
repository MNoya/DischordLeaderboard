import { HelpCircle } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { Tooltip } from "./Tooltip";
import { SCORING_HASH } from "./ScoringModal";
import { cn } from "../lib/utils";

// Opens the scoring explanation by adding the #points hash; the modal itself is
// rendered once by <ScoringModalHost>. Icon-only by default (with an "About
// Points" tooltip); pass `label` for the text-label variant used in the points
// breakdown, which drops the tooltip since the label is self-explanatory.
export function ScoringInfoButton({
  className,
  size = 14,
  label,
}: {
  className?: string;
  size?: number;
  label?: string;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const open = () => navigate(`${location.pathname}${location.search}${SCORING_HASH}`);

  const button = (
    <button
      type="button"
      onClick={open}
      aria-label={label ?? "About Points"}
      className={cn(
        "inline-flex items-center justify-center cursor-pointer transition-colors",
        label
          ? "gap-1.5 text-muted hover:text-green font-display tracking-[0.10em] text-[12px] leading-none whitespace-nowrap"
          : "text-muted hover:text-green",
        className,
      )}
    >
      <HelpCircle size={size} strokeWidth={2} />
      {label ? <span>{label}</span> : null}
    </button>
  );

  if (label) {
    return button;
  }
  return <Tooltip label="About Points">{button}</Tooltip>;
}
