import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ALogo, AWordmark } from "./Brand";
import { cn } from "../lib/utils";
import { useIsMobile } from "../lib/use-is-mobile";

// Top-of-page chrome. Designed to feel like its own product but small enough
// that a future LLU site shell can wrap or omit it cleanly.

const NAV: Array<{ label: string; to: string; match: (path: string) => boolean }> = [
  { label: "LEADERBOARD", to: "/", match: (p) => p === "/" || /^\/[A-Z0-9]{2,4}$/.test(p) },
  { label: "ABOUT", to: "/about", match: (p) => p.startsWith("/about") },
];

export function AppHeader({ subtitle = "LEADERBOARD" }: { subtitle?: string }) {
  const loc = useLocation();
  const isMobile = useIsMobile();
  const [menuOpen, setMenuOpen] = useState(false);

  // Close the mobile menu whenever the route changes so it doesn't linger
  // after a tap.
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

  return (
    <header
      className={cn(
        "border-b border-border flex items-center justify-between bg-bg shrink-0 relative",
        isMobile ? "py-2.5 px-4" : "py-4 px-10",
      )}
    >
      <Link
        to="/"
        className={cn(
          "flex items-center no-underline",
          isMobile ? "gap-2.5" : "gap-3.5",
        )}
      >
        <ALogo size={isMobile ? 34 : 64} />
        <AWordmark size={isMobile ? "sm" : "lg"} subtitle={subtitle} />
      </Link>

      {!isMobile && (
        <nav className="flex gap-1.5 font-display text-[14px] tracking-[0.14em]">
          {NAV.map((n) => {
            const active = n.match(loc.pathname);
            return (
              <Link
                key={n.label}
                to={n.to}
                className={cn(
                  "py-1.5 px-3.5 no-underline border transition-colors",
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

      {isMobile && (
        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          className={cn(
            "w-7 h-7 border flex items-center justify-center cursor-pointer transition-colors",
            menuOpen ? "border-green text-green bg-surface" : "border-border2 text-muted bg-transparent",
          )}
        >
          <span className="text-[16px] leading-none">{menuOpen ? "×" : "≡"}</span>
        </button>
      )}

      {isMobile && menuOpen && (
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
        className="fixed inset-0 top-[60px] bg-black/60 z-30"
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
                "py-3.5 px-4 no-underline font-display text-[14px] tracking-[0.18em] border-b border-border transition-colors",
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
