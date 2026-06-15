import { useEffect, useState } from "react";
import { ArrowUp } from "./Icons";
import { cn } from "../lib/utils";

export function GoToTopButton({
  onClick,
  threshold = 600,
  compact = false,
  bottomClass = "bottom-4 md:bottom-6",
}: {
  onClick: () => void;
  threshold?: number;
  compact?: boolean;
  bottomClass?: string;
}) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > threshold);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [threshold]);
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Go to top"
      className={cn(
        "fixed z-30 left-1/2 -translate-x-1/2 inline-flex items-center gap-2 bg-surface border border-border2 text-text font-display tracking-[0.18em] shadow-lg cursor-pointer transition-opacity hover:bg-surface2",
        bottomClass,
        compact ? "px-3 py-2 text-[11px]" : "px-4 py-2.5 text-[12px]",
        visible ? "opacity-100" : "opacity-0 pointer-events-none",
      )}
    >
      <ArrowUp size={14} />
      TOP
    </button>
  );
}
