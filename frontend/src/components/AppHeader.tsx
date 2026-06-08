import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ALogo, AWordmark } from "./Brand";
import { cn } from "../lib/utils";
import { useIsMobile } from "../lib/use-is-mobile";

// Top-of-page chrome. Designed to feel like its own product but small enough
// that a future LLU site shell can wrap or omit it cleanly.

const NAV: Array<{ label: string; to: string; match: (path: string) => boolean }> = [
  { label: "LEADERBOARD", to: "/leaderboard", match: (p) => p === "/" || p === "/leaderboard" || p.startsWith("/leaderboard/") },
  { label: "POD DRAFTS", to: "/pods", match: (p) => p.startsWith("/pods") },
  { label: "TIER LIST", to: "/tier-list", match: (p) => p.startsWith("/tier-list") },
  { label: "ABOUT", to: "/about", match: (p) => p.startsWith("/about") },
];

const NAV_ITEM_CLASS = "py-2.5 px-5 no-underline border transition-colors whitespace-nowrap";

export function AppHeader({ subtitle = "LEADERBOARD" }: { subtitle?: string }) {
  const loc = useLocation();
  const isMobile = useIsMobile();
  const [menuOpen, setMenuOpen] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(false);
  const brandHref = /^\/pods\/[^/]+/.test(loc.pathname) ? "/pods" : "/";

  const headerRef = useRef<HTMLElement>(null);
  const brandRef = useRef<HTMLAnchorElement>(null);
  const navMeasureRef = useRef<HTMLDivElement>(null);

  // Close the open menu whenever the route changes so it doesn't linger.
  useEffect(() => {
    setMenuOpen(false);
  }, [loc.pathname]);

  // Lock body scroll while the slide-in menu is open.
  useEffect(() => {
    if (!menuOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [menuOpen]);

  // Collapse the inline nav to a menu whenever brand + nav can't share one row,
  // so adding categories never needs a hand-tuned breakpoint.
  useLayoutEffect(() => {
    const header = headerRef.current;
    const brand = brandRef.current;
    const measure = navMeasureRef.current;
    if (!header || !brand || !measure) return;
    const GAP_BETWEEN = 32;
    const evaluate = () => {
      const styles = getComputedStyle(header);
      const avail = header.clientWidth - parseFloat(styles.paddingLeft) - parseFloat(styles.paddingRight);
      const required = brand.scrollWidth + measure.scrollWidth + GAP_BETWEEN;
      setNavCollapsed(required > avail);
    };
    const ro = new ResizeObserver(evaluate);
    ro.observe(header);
    ro.observe(brand);
    ro.observe(measure);
    evaluate();
    return () => ro.disconnect();
  }, [isMobile, subtitle]);

  return (
    <header
      ref={headerRef}
      className={cn(
        "border-b border-border flex items-center justify-between bg-bg shrink-0 relative",
        isMobile ? "py-1.5 px-3" : "py-4 pl-10 pr-6",
      )}
    >
      <Link
        ref={brandRef}
        to={brandHref}
        className={cn(
          "flex items-center no-underline shrink-0",
          isMobile ? "gap-3" : "gap-6 pl-[13px]",
        )}
      >
        <div
          className="flex items-center justify-center shrink-0 overflow-visible"
          style={{ height: isMobile ? 40 : 64 }}
        >
          <ALogo size={isMobile ? 36 : 55} />
        </div>
        <AWordmark size={isMobile ? "sm" : "lg"} subtitle={subtitle} />
      </Link>

      <div
        ref={navMeasureRef}
        aria-hidden="true"
        className="absolute -left-[9999px] top-0 flex gap-2 font-display text-[19px] tracking-[0.14em]"
      >
        {NAV.map((n) => (
          <span key={n.label} className={NAV_ITEM_CLASS}>
            {n.label}
          </span>
        ))}
      </div>

      {!navCollapsed && (
        <nav className="flex gap-2 font-display text-[19px] tracking-[0.14em]">
          {NAV.map((n) => {
            const active = n.match(loc.pathname);
            return (
              <Link
                key={n.label}
                to={n.to}
                className={cn(
                  NAV_ITEM_CLASS,
                  active
                    ? "text-bg bg-green border-green"
                    : "text-text border-transparent hover:bg-surface",
                )}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
      )}

      {navCollapsed && (
        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          className={cn(
            "w-11 h-11 border flex items-center justify-center cursor-pointer transition-colors",
            menuOpen ? "border-green text-green bg-surface" : "border-border2 text-muted bg-transparent",
          )}
        >
          <span className="text-[28px] leading-none">{menuOpen ? "×" : "≡"}</span>
        </button>
      )}

      {navCollapsed && menuOpen && (
        <MobileMenu pathname={loc.pathname} onClose={() => setMenuOpen(false)} />
      )}
    </header>
  );
}

function MobileMenu({ pathname, onClose }: { pathname: string; onClose: () => void }) {
  return (
    <>
      <div
        onClick={onClose}
        className="absolute top-full left-0 right-0 h-screen bg-black/60 z-30"
        aria-hidden="true"
      />
      <nav
        className="absolute top-full right-0 left-0 bg-bg border-b border-border z-40 flex flex-col"
        role="menu"
      >
        {NAV.map((n) => {
          const active = n.match(pathname);
          return (
            <Link
              key={n.label}
              to={n.to}
              role="menuitem"
              className={cn(
                "flex items-center min-h-[54px] px-5 no-underline font-display text-[17px] tracking-[0.14em] border-b border-border transition-colors",
                active ? "bg-green text-bg" : "text-text bg-transparent hover:bg-surface",
              )}
            >
              {n.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
