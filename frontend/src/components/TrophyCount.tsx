import { Trophy } from "./Brand";
import { cn } from "../lib/utils";

// Trophy icon + count, used wherever the marquee stat shows up. Sizes track the
// row contexts where it appears (compact = inline mini-rows; sm = sidebar
// captions; md = main leaderboard row).

export function TrophyCount({
  count,
  size = "sm",
  fixedDigits,
  className,
}: {
  count: number;
  size?: "compact" | "sm" | "md";
  fixedDigits?: number;
  className?: string;
}) {
  const trophySize = size === "compact" ? 10 : size === "sm" ? 12 : 14;
  const fontSize = size === "compact" ? "text-[10px]" : size === "sm" ? "text-[11px]" : "text-[15px]";
  const fontWeight = size === "md" ? "font-semibold" : "";
  const countStyle = fixedDigits
    ? { display: "inline-block", minWidth: `${fixedDigits}ch`, textAlign: "right" as const }
    : undefined;
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <Trophy size={trophySize} color="#ffc63a" />
      <span className={cn("mono", fontSize, fontWeight)} style={countStyle}>
        {count}
      </span>
    </span>
  );
}
