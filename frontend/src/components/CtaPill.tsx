import type { ReactNode } from "react";
import { ArrowRight } from "./Icons";
import { cn } from "../lib/utils";

// The green right-leaning CTA pill with a trailing arrow, shared by the About,
// Pod Drafts, and 404 pages. Renders a <span> so it can sit inside whatever
// interactive wrapper the caller already has (an <a>, a <Link>, or a row Link).
//
// The chamfer is point-symmetric (top-left and bottom-right cut equally), so the
// icon-less variant uses symmetric padding to read as centred; the icon variant
// leans its padding left because the icon circle fills the chamfered corner.
//
// `clip-path` has no Tailwind utility so it stays inline.

type CtaSize = "sm" | "md" | "lg";

const SIZES: Record<CtaSize, {
  base: string;
  padWithIcon: string;
  padBare: string;
  label: string;
  circle: string;
  arrow: number;
}> = {
  sm: {
    base: "gap-3 py-2",
    padWithIcon: "pl-3.5 pr-5",
    padBare: "px-5",
    label: "text-[15px] tracking-[0.10em]",
    circle: "w-7 h-7",
    arrow: 14,
  },
  md: {
    base: "gap-3 md:gap-4 py-2.5 md:py-3",
    padWithIcon: "pl-5 md:pl-6 pr-6 md:pr-8",
    padBare: "pl-9 pr-5 md:pl-10 md:pr-6",
    label: "text-[16px] md:text-[18px] tracking-[0.14em]",
    circle: "w-9 h-9 md:w-10 md:h-10",
    arrow: 18,
  },
  lg: {
    base: "gap-3 md:gap-4 py-2.5 md:py-3",
    padWithIcon: "pl-5 md:pl-6 pr-6 md:pr-8",
    padBare: "px-7 md:px-8",
    label: "text-[17px] md:text-[20px] tracking-[0.14em]",
    circle: "w-9 h-9 md:w-10 md:h-10",
    arrow: 18,
  },
};

const CHAMFER = "polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)";

export function CtaPill({
  children,
  size = "md",
  icon,
  hover = "self",
  className,
}: {
  children: ReactNode;
  size?: CtaSize;
  icon?: ReactNode;
  hover?: "self" | "group";
  className?: string;
}) {
  const s = SIZES[size];
  return (
    <span
      className={cn(
        "bg-green text-bg inline-flex items-center transition-colors border-none",
        s.base,
        icon ? s.padWithIcon : s.padBare,
        hover === "group" ? "group-hover:bg-green-2" : "hover:bg-green-2",
        className,
      )}
      style={{ clipPath: CHAMFER }}
    >
      {icon && (
        <span
          className={cn(
            "inline-flex items-center justify-center rounded-full bg-bg text-text shrink-0",
            s.circle,
          )}
        >
          {icon}
        </span>
      )}
      <span className={cn("font-display leading-none", s.label)}>{children}</span>
      <ArrowRight size={s.arrow} />
    </span>
  );
}
