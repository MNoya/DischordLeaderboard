import React from "react";

// Single source of truth for the responsive cutover. Pages and the header all
// consult this so layouts stay in sync. Lives in /lib so React Fast Refresh
// doesn't complain about mixed component+hook exports.

export function useIsMobile(breakpoint = 720): boolean {
  const [isMobile, setIsMobile] = React.useState<boolean>(
    typeof window !== "undefined" ? window.innerWidth < breakpoint : false
  );
  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const handler = (e: MediaQueryListEvent | MediaQueryList) => setIsMobile(e.matches);
    handler(mql);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [breakpoint]);
  return isMobile;
}

const SET_HIDE_BREAKPOINTS: Array<[number, number]> = [
  [1400, 2],
  [1100, 3],
];

const VISIBLE_FLOOR = 2;

function computeHideCount(): number {
  if (typeof window === "undefined") return 4;
  for (const [w, hide] of SET_HIDE_BREAKPOINTS) {
    if (window.matchMedia(`(min-width: ${w}px)`).matches) return hide;
  }
  return 4;
}

export function useSetVisibleCap(total: number, extraHide = 0): number {
  const [hide, setHide] = React.useState<number>(computeHideCount);
  React.useEffect(() => {
    const mqls = SET_HIDE_BREAKPOINTS.map(([w]) =>
      window.matchMedia(`(min-width: ${w}px)`),
    );
    const update = () => setHide(computeHideCount());
    mqls.forEach((m) => m.addEventListener("change", update));
    update();
    return () => mqls.forEach((m) => m.removeEventListener("change", update));
  }, []);
  return Math.max(VISIBLE_FLOOR, total - hide - extraHide);
}
