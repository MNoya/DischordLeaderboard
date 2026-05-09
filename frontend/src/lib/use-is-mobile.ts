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
