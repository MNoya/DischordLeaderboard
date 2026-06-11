import type { EpisodeCategory } from "../data/episodes";
import { cn } from "../lib/utils";

const CATEGORY_STYLE: Record<EpisodeCategory, string> = {
  "Set Primer": "bg-green text-bg",
  "Set Review": "bg-teal text-bg",
  "Draft-along": "bg-red text-bg",
  Sunset: "bg-gold text-bg",
  "Q&A": "border border-border2 text-subtle",
  Strategy: "border border-border2 text-subtle",
};

export function CategoryTag({ category, className }: { category: EpisodeCategory; className?: string }) {
  return (
    <span
      className={cn(
        "inline-block font-display tracking-[0.16em] uppercase text-[11px] leading-none px-2 py-1",
        CATEGORY_STYLE[category],
        className,
      )}
    >
      {category}
    </span>
  );
}
