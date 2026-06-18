import { useEffect, type RefObject } from "react";

const SWIPE_EDGE_ZONE = 32;
const SWIPE_DIRECTION_SLOP = 10;
const DRAWER_FALLBACK_WIDTH = 240;

// Drives a left-anchored drawer from touch: opens on an edge swipe, closes on a
// left swipe while open, and reports live 0→1 progress so the panel can track
// the finger. `preventDefault` on the confirmed-horizontal move suppresses the
// browser's edge back-navigation; passive listeners cannot.
export function useDrawerSwipe(
  open: boolean,
  setOpen: (value: boolean) => void,
  setDrag: (value: number | null) => void,
  panelRef: RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    const isMobile = () => window.matchMedia("(max-width: 1023px)").matches;
    let startX = 0;
    let startY = 0;
    let tracking = false;
    let horizontal = false;
    let width = DRAWER_FALLBACK_WIDTH;
    let frame = 0;
    let pending: number | null = null;

    const flush = () => {
      frame = 0;
      if (pending !== null) {
        setDrag(pending);
      }
    };
    const scheduleDrag = (progress: number) => {
      pending = progress;
      if (!frame) {
        frame = requestAnimationFrame(flush);
      }
    };
    const progressFor = (dx: number) => {
      const traveled = open ? width + dx : dx;
      return Math.max(0, Math.min(1, traveled / width));
    };

    const onTouchStart = (event: TouchEvent) => {
      horizontal = false;
      tracking = false;
      if (!isMobile() || event.touches.length !== 1) {
        return;
      }
      startX = event.touches[0].clientX;
      startY = event.touches[0].clientY;
      tracking = open || startX <= SWIPE_EDGE_ZONE;
    };

    const onTouchMove = (event: TouchEvent) => {
      if (!tracking) {
        return;
      }
      const dx = event.touches[0].clientX - startX;
      const dy = event.touches[0].clientY - startY;
      if (!horizontal) {
        if (Math.abs(dx) < SWIPE_DIRECTION_SLOP && Math.abs(dy) < SWIPE_DIRECTION_SLOP) {
          return;
        }
        if (Math.abs(dy) >= Math.abs(dx)) {
          tracking = false;
          return;
        }
        horizontal = true;
        width = panelRef.current?.offsetWidth || DRAWER_FALLBACK_WIDTH;
      }
      event.preventDefault();
      scheduleDrag(progressFor(dx));
    };

    const onTouchEnd = (event: TouchEvent) => {
      if (frame) {
        cancelAnimationFrame(frame);
        frame = 0;
      }
      if (!tracking || !horizontal) {
        tracking = false;
        return;
      }
      tracking = false;
      const progress = progressFor(event.changedTouches[0].clientX - startX);
      setDrag(null);
      setOpen(progress > 0.5);
    };

    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onTouchEnd);
      if (frame) {
        cancelAnimationFrame(frame);
      }
    };
  }, [open, setOpen, setDrag, panelRef]);
}
