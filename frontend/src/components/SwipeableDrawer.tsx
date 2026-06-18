import { useRef, useState, type ReactNode } from "react";
import { useDrawerSwipe } from "../hooks/useDrawerSwipe";
import { cn } from "../lib/utils";

// Left-anchored mobile drawer (lg:hidden) with a dimming scrim. Opens/closes
// via edge-swipe gestures (see useDrawerSwipe) and tracks the finger live, then
// snaps past the halfway point. Tap the scrim or swipe left to close.
export function SwipeableDrawer({
  open,
  onOpenChange,
  closeLabel,
  className,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  closeLabel: string;
  className?: string;
  children: ReactNode;
}) {
  const [drag, setDrag] = useState<number | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useDrawerSwipe(open, onOpenChange, setDrag, panelRef);

  return (
    <div className={cn("lg:hidden fixed inset-0 z-30", open || drag !== null ? "" : "pointer-events-none")}>
      <button
        type="button"
        aria-label={closeLabel}
        onClick={() => onOpenChange(false)}
        style={drag !== null ? { opacity: drag } : undefined}
        className={cn(
          "absolute inset-0 w-full bg-bg/70 transition-opacity duration-300",
          drag !== null && "transition-none",
          open ? "opacity-100" : "opacity-0 pointer-events-none",
        )}
      />
      <div
        ref={panelRef}
        style={drag !== null ? { transform: `translateX(${(drag - 1) * 100}%)` } : undefined}
        className={cn(
          "absolute inset-y-0 left-0 w-[240px] max-w-[72vw] overflow-y-auto bg-surface border-r border-border",
          "transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
          drag !== null && "transition-none",
          open ? "translate-x-0" : "-translate-x-full",
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}
