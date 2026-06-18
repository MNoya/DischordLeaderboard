import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, LogOut } from "lucide-react";
import { DiscordIcon } from "./BrandIcons";
import { ALogo, AWordmark } from "./Brand";
import { cn } from "../lib/utils";
import { useIsMobile } from "../lib/use-is-mobile";
import { useAuth } from "../auth/useAuth";
import { useP0P1Picks } from "../data/hooks";
import { P0P1_SET_CODE, P0P1_VOTING_DEADLINE, SLOTS } from "../data/p0p1Slots";

// Top-of-page chrome shared across the whole community site. The brand mark is
// the Home link; each section is a nav tab.

const NAV: Array<{ label: string; badge?: (props: { active: boolean }) => JSX.Element | null; to: string; match: (path: string) => boolean }> = [
  { label: "P0 P1", badge: P0P1Badge, to: "/p0p1", match: (p) => p.startsWith("/p0p1") },
  { label: "EPISODES", to: "/episodes", match: (p) => p.startsWith("/episodes") },
  { label: "TIER LIST", to: "/tier-list", match: (p) => p.startsWith("/tier-list") },
  { label: "LEADERBOARD", to: "/leaderboard", match: (p) => p === "/leaderboard" || p.startsWith("/leaderboard/") },
  { label: "POD DRAFTS", to: "/pods", match: (p) => p.startsWith("/pods") },
  { label: "COMMUNITY", to: "/community", match: (p) => p.startsWith("/community") },
];

const NAV_ITEM_CLASS = "h-12 px-5 inline-flex items-center no-underline border transition-colors whitespace-nowrap";

export function AppHeader({ subtitle = "LEADERBOARD", fill = false }: { subtitle?: string; fill?: boolean }) {
  const loc = useLocation();
  const isMobile = useIsMobile();
  const [menuOpen, setMenuOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(NAV.length);
  const brandHref = "/";

  const headerRef = useRef<HTMLElement>(null);
  const brandRef = useRef<HTMLAnchorElement>(null);
  const navMeasureRef = useRef<HTMLDivElement>(null);
  const authMeasureRef = useRef<HTMLSpanElement>(null);

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

  // Show as many leading nav tabs as share the row with brand + auth; the rest
  // spill into the menu. So adding categories never needs a hand-tuned breakpoint.
  useLayoutEffect(() => {
    const header = headerRef.current;
    const brand = brandRef.current;
    const measure = navMeasureRef.current;
    const authMeasure = authMeasureRef.current;
    if (!header || !brand || !measure) return;
    const GAP_BRAND = 32;
    const GROUP_GAP = 4;
    const NAV_GAP = 8;
    const MENU_BUTTON = 48;
    const evaluate = () => {
      if (isMobile) {
        setVisibleCount(0);
        return;
      }
      const styles = getComputedStyle(header);
      const avail = header.clientWidth - parseFloat(styles.paddingLeft) - parseFloat(styles.paddingRight);
      const authWidth = authMeasure ? authMeasure.scrollWidth : 0;
      const itemWidths = Array.from(measure.children).map((el) => (el as HTMLElement).scrollWidth);
      const navWidth = (k: number) =>
        k === 0 ? 0 : itemWidths.slice(0, k).reduce((sum, w) => sum + w, 0) + NAV_GAP * (k - 1);
      const fits = (k: number, withMenu: boolean) => {
        const tabs = navWidth(k) + (k > 0 ? GROUP_GAP : 0);
        const menu = withMenu ? GROUP_GAP + MENU_BUTTON : 0;
        return brand.scrollWidth + GAP_BRAND + tabs + authWidth + menu <= avail;
      };
      if (fits(itemWidths.length, false)) {
        setVisibleCount(itemWidths.length);
        return;
      }
      let count = itemWidths.length - 1;
      while (count > 0 && !fits(count, true)) {
        count--;
      }
      setVisibleCount(count);
    };
    const ro = new ResizeObserver(evaluate);
    ro.observe(header);
    ro.observe(brand);
    ro.observe(measure);
    evaluate();
    return () => ro.disconnect();
  }, [isMobile, subtitle]);

  const hasMenu = isMobile || visibleCount < NAV.length;

  useEffect(() => {
    if (!hasMenu) setMenuOpen(false);
  }, [hasMenu]);

  return (
    <header
      ref={headerRef}
      className={cn(
        "border-b border-border flex items-center justify-between bg-bg shrink-0 relative",
        isMobile ? "py-1.5 px-3" : "py-4 pl-10 pr-6",
      )}
      style={fill && !isMobile ? { paddingRight: "calc(1.5rem + var(--app-scrollbar, 0px))" } : undefined}
    >
      <Link
        ref={brandRef}
        to={brandHref}
        className={cn(
          "flex items-center no-underline shrink-0",
          isMobile ? "gap-3 pl-2" : "gap-6 pl-[13px]",
        )}
      >
        <div
          className="flex items-center justify-center shrink-0 overflow-visible"
          style={{ height: isMobile ? 44 : 64 }}
        >
          <ALogo size={isMobile ? 42 : 55} />
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
      <span
        ref={authMeasureRef}
        aria-hidden="true"
        className={cn("absolute -left-[9999px] top-0 font-display text-[19px] tracking-[0.14em]", NAV_ITEM_CLASS)}
      >
        LOG IN
      </span>

      <div className="flex items-center gap-1">
        {!isMobile && visibleCount > 0 && (
          <nav className="flex gap-2 font-display text-[19px] tracking-[0.14em]">
            {NAV.slice(0, visibleCount).map((n) => {
              const active = n.match(loc.pathname);
              return (
                <Link
                  key={n.label}
                  to={n.to}
                  className={cn(
                    NAV_ITEM_CLASS,
                    n.badge && "relative",
                    active
                      ? "text-bg bg-green border-green"
                      : "text-text border-transparent hover:bg-surface hover:text-green",
                  )}
                >
                  {n.label}
                  {n.badge && <n.badge active={active} />}
                </Link>
              );
            })}
          </nav>
        )}
        {!isMobile && <DesktopAuth />}

        {hasMenu && (
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            className={cn(
              "w-12 h-12 border flex items-center justify-center cursor-pointer transition-colors",
              menuOpen ? "border-green text-green bg-surface" : "border-border2 text-muted bg-transparent",
            )}
          >
            <span className="text-[28px] leading-none">{menuOpen ? "×" : "≡"}</span>
          </button>
        )}
      </div>

      {hasMenu && menuOpen && (
        <MobileMenu
          items={isMobile ? NAV : NAV.slice(visibleCount)}
          includeAuth={isMobile}
          pathname={loc.pathname}
          onClose={() => setMenuOpen(false)}
        />
      )}
    </header>
  );
}

function DesktopAuth() {
  const { user, loading, signIn, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  if (loading) return null;

  if (!user) {
    return (
      <button
        type="button"
        onClick={signIn}
        className={cn(
          NAV_ITEM_CLASS,
          "inline-flex items-center gap-2.5 font-display text-[19px] tracking-[0.14em] cursor-pointer text-text border-border hover:bg-surface bg-transparent",
        )}
      >
        <DiscordIcon size={19} />
        LOG IN
      </button>
    );
  }

  const avatar = (size: string, text: string) =>
    user.avatarUrl ? (
      <img src={user.avatarUrl} alt="" className={cn(size, "rounded-full")} />
    ) : (
      <div className={cn(size, "rounded-full bg-surface2 flex items-center justify-center text-subtle font-semibold", text)}>
        {user.username.charAt(0).toUpperCase()}
      </div>
    );

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex items-center gap-2.5 cursor-pointer bg-transparent border rounded-full pl-1.5 pr-2.5 py-1.5 transition-colors",
          open ? "bg-surface border-border" : "border-transparent hover:bg-surface hover:border-border",
        )}
      >
        {avatar("w-9 h-9", "text-[15px]")}
        <span className="text-text text-[15px] font-medium max-w-[160px] truncate">{user.username}</span>
        <ChevronDown size={16} className={cn("text-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-60 bg-surface border border-border2 rounded-lg shadow-xl shadow-black/40 overflow-hidden z-50 animate-fadeUpIn">
          <div className="flex items-center gap-2.5 px-3 py-3 border-b border-border">
            {avatar("w-8 h-8", "text-sm")}
            <span className="text-text text-sm font-medium truncate">{user.username}</span>
          </div>
          <button
            type="button"
            onClick={() => { signOut(); setOpen(false); }}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-subtle hover:bg-surface2 hover:text-text cursor-pointer bg-transparent border-none transition-colors"
          >
            <LogOut size={16} />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}

function MobileMenu({
  items,
  includeAuth,
  pathname,
  onClose,
}: {
  items: typeof NAV;
  includeAuth: boolean;
  pathname: string;
  onClose: () => void;
}) {
  const { user, loading, signIn, signOut } = useAuth();

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
        {includeAuth && !loading && user && (
          <div className="flex items-center gap-3 px-5 min-h-[54px] border-b border-border">
            {user.avatarUrl ? (
              <img src={user.avatarUrl} alt="" className="w-6 h-6 rounded-full" />
            ) : (
              <div className="w-6 h-6 rounded-full bg-surface" />
            )}
            <span className="text-text text-sm truncate">{user.username}</span>
          </div>
        )}
        {items.map((n) => {
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
              {n.badge && <MobileBadgeSlot active={active} />}
            </Link>
          );
        })}
        {includeAuth && !loading && !user && (
          <button
            type="button"
            onClick={() => { signIn(); onClose(); }}
            role="menuitem"
            className="flex items-center min-h-[54px] px-5 font-display text-[17px] tracking-[0.14em] border-b border-border transition-colors text-text bg-transparent hover:bg-surface cursor-pointer border-x-0 border-t-0"
          >
            LOG IN
          </button>
        )}
        {includeAuth && !loading && user && (
          <button
            type="button"
            onClick={() => { signOut(); onClose(); }}
            role="menuitem"
            className="flex items-center min-h-[54px] px-5 text-sm text-muted bg-transparent hover:bg-surface cursor-pointer border-x-0 border-t-0 border-b border-border"
          >
            LOG OUT
          </button>
        )}
      </nav>
    </>
  );
}

function useP0P1BadgeState() {
  const { user } = useAuth();
  const { data: picks } = useP0P1Picks(user ? P0P1_SET_CODE : undefined);
  const isPastDeadline = new Date() > P0P1_VOTING_DEADLINE;
  const filled = user ? (picks?.length ?? 0) : 0;
  return { user, isPastDeadline, filled, total: SLOTS.length };
}

function P0P1Badge({ active }: { active: boolean }) {
  const { user, isPastDeadline, filled, total } = useP0P1BadgeState();

  if (isPastDeadline) return null;

  const pill = cn(
    "absolute -top-1.5 -right-1.5 z-10 rounded-full border border-green px-1.5 py-0.5 text-[9px] leading-none font-sans font-bold tracking-wide",
    active ? "bg-bg text-green" : "bg-green text-bg",
  );

  if (!user || filled === 0) return <span className={pill}>OPEN</span>;
  if (filled === total) return <span className={pill}>✓</span>;
  return <span className={pill}>{filled}/{total}</span>;
}

function MobileBadgeSlot({ active }: { active: boolean }) {
  const { user, isPastDeadline, filled, total } = useP0P1BadgeState();

  if (isPastDeadline) return null;

  const wrap = cn("ml-2 text-[10px] font-semibold font-sans tracking-normal", active ? "text-bg/80" : "text-green");

  if (!user || filled === 0) return <span className={wrap}>・OPEN</span>;
  if (filled === total) return <span className={wrap}>✓</span>;
  return <span className={wrap}>{filled}/{total}</span>;
}
