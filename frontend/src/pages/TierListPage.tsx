import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { ALogo, SetGlyph, setGlyphCode } from "../components/Brand";
import { SetSwitcherDesktop, SetSwitcherMobile } from "../components/SetSwitcher";
import { useSets } from "../data/hooks";
import { useIsLandscapePhone, useIsMobile } from "../lib/use-is-mobile";
import {
  ACTIVE_SET_CODE,
  TIER_LIST_EMBED_BASE,
  TIER_LIST_EMBED_HEIGHT,
  TIER_LIST_EMBED_MOBILE_WIDTH,
  TIER_LIST_UIDS,
} from "../data/constants";

export function TierListPage() {
  const { data: sets } = useSets();
  const isMobile = useIsMobile();
  const landscapePhone = useIsLandscapePhone();
  const [picked, setPicked] = useState<string | null>(null);
  const [reportedHeight, setReportedHeight] = useState<number | null>(null);
  const [headerHidden, setHeaderHidden] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const liveSet = sets?.find((s) => s.isActive)?.code ?? ACTIVE_SET_CODE;
  const current = picked ?? liveSet;
  const setMeta = sets?.find((s) => s.code === current);
  const uid = TIER_LIST_UIDS[current];
  const tierListSets = (sets ?? []).filter((s) => TIER_LIST_UIDS[s.code]);

  useEffect(() => {
    setReportedHeight(null);
  }, [uid]);

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== "https://www.17lands.com") return;
      const data = e.data;
      if (data && data.type === "tier-list-height" && typeof data.height === "number") {
        setReportedHeight(data.height);
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const io = new IntersectionObserver(([entry]) => setHeaderHidden(!entry.isIntersecting));
    io.observe(sentinel);
    return () => io.disconnect();
  }, []);

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="TIER LIST" />
      <main className="flex flex-col w-full px-[15px] pb-4">
        <div ref={sentinelRef} className="h-0" aria-hidden="true" />
        <div className="sticky top-0 z-20 bg-bg flex items-center justify-between gap-3 py-2 md:py-3 relative">
          <h1 className="font-display tracking-[0.12em] flex items-center gap-2 md:gap-3 leading-none min-w-0">
            <SetGlyph code={setMeta ? setGlyphCode(setMeta) : current} size={isMobile ? 26 : 38} />
            <span className="text-[17px] md:text-[30px] truncate">
              {setMeta?.name?.toUpperCase() ?? current}
            </span>
            {headerHidden && (
              <span className="text-green text-[14px] md:text-[24px] shrink-0">TIER LIST</span>
            )}
          </h1>
          {headerHidden && !isMobile && (
            <Link
              to="/"
              aria-label="Limited Level-Ups"
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 no-underline"
            >
              <ALogo size={40} />
            </Link>
          )}
          {tierListSets.length > 1 &&
            (isMobile ? (
              <div className="w-[124px] shrink-0">
                <SetSwitcherMobile sets={tierListSets} activeCode={current} onChange={setPicked} />
              </div>
            ) : (
              <SetSwitcherDesktop
                sets={tierListSets}
                activeCode={current}
                onChange={setPicked}
                extraHide={landscapePhone ? 2 : 0}
              />
            ))}
        </div>

        {uid ? (
          <div className={`w-full border border-border bg-surface ${isMobile ? "overflow-x-auto" : "overflow-hidden"}`}>
            <iframe
              src={`${TIER_LIST_EMBED_BASE}/${uid}?filters=true`}
              title={`${setMeta?.name ?? current} tier list`}
              className="block border-0"
              style={{
                marginLeft: -30,
                width: isMobile ? TIER_LIST_EMBED_MOBILE_WIDTH + 30 : "calc(100% + 65px)",
                height: reportedHeight ?? TIER_LIST_EMBED_HEIGHT,
              }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center border border-border bg-surface text-muted text-[14px] min-h-[300px]">
            No tier list is available for {current} yet.
          </div>
        )}

        <div className="pt-2 text-right">
          <a
            href={`https://www.17lands.com/tier_list/${uid ?? ""}`}
            target="_blank"
            rel="noreferrer"
            className="mono text-[10px] md:text-[12px] text-muted hover:text-green transition-colors no-underline"
          >
            via 17Lands
          </a>
        </div>
      </main>
    </div>
  );
}
