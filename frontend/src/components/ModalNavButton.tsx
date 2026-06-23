import { cn } from "../lib/utils";

const CHEVRON_PATH: Record<"prev" | "next", string> = {
  prev: "M15 18l-6-6 6-6",
  next: "M9 6l6 6 -6 6",
};

export function ModalNavButton({
  dir,
  onClick,
  label,
  srLabel,
}: {
  dir: "prev" | "next";
  onClick?: () => void;
  label?: string;
  srLabel?: string;
}) {
  const chevron = (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={CHEVRON_PATH[dir]} />
    </svg>
  );
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      aria-label={label ? undefined : srLabel}
      className={cn(
        "flex items-center justify-center border border-white/40 text-text",
        "transition-[transform,background-color,border-color] duration-150 ease-out",
        "touch-manipulation [-webkit-tap-highlight-color:transparent]",
        label
          ? "h-10 gap-2 rounded-lg px-3 font-display text-[14px] tracking-[0.14em]"
          : "h-10 w-10 rounded-lg",
        onClick
          ? "hover:border-white/60 hover:bg-white/10 active:scale-90 active:bg-white/20 motion-reduce:active:scale-100"
          : "opacity-30",
      )}
    >
      {dir === "prev" && chevron}
      {label?.toUpperCase()}
      {dir === "next" && chevron}
    </button>
  );
}
