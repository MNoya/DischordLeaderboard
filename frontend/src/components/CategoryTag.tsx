import type { EpisodeCategory } from "../data/episodes";
import { cn } from "../lib/utils";

const CATEGORY_STYLE: Record<EpisodeCategory, string> = {
  "First Impressions": "bg-green text-bg",
  "Set Review": "bg-teal text-bg",
  Draft: "bg-red text-bg",
  Metagame: "bg-gold text-bg",
  Evergreen: "bg-border2 text-text",
};

export function CategoryTag({ category, className }: { category: EpisodeCategory; className?: string }) {
  return (
    <span
      className={cn(
        "inline-block font-display tracking-[0.14em] uppercase text-[12.5px] leading-none px-2 py-1",
        CATEGORY_STYLE[category],
        className,
      )}
    >
      {category}
    </span>
  );
}
