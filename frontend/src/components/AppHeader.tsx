import { Link, useLocation } from "react-router-dom";
import { ALogo, AWordmark } from "./Brand";
import { cn } from "../lib/utils";
import { useIsMobile } from "../lib/use-is-mobile";

// Top-of-page chrome. Designed to feel like its own product but small enough
// that a future LLU site shell can wrap or omit it cleanly.

const NAV: Array<{ label: string; to: string; match: (path: string) => boolean }> = [
  { label: "LEADERBOARD", to: "/", match: (p) => p === "/" || /^\/[A-Z0-9]{2,4}$/.test(p) },
  { label: "ARCHETYPES", to: "/archetypes", match: (p) => p.startsWith("/archetypes") },
  { label: "PLAYERS", to: "/players", match: (p) => p.startsWith("/player") },
];

export function AppHeader({ subtitle = "LEADERBOARD" }: { subtitle?: string }) {
  const loc = useLocation();
  const isMobile = useIsMobile();

  return (
    <header
      className={cn(
        "border-b border-border flex items-center justify-between bg-bg shrink-0",
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
        <div className="w-7 h-7 border border-border2 flex items-center justify-center">
          <span className="text-[14px] text-muted">≡</span>
        </div>
      )}
    </header>
  );
}

