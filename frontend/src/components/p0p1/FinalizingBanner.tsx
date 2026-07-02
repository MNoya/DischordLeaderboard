export function FinalizingBanner({ showingMidway }: { showingMidway: boolean }) {
  return (
    <div className="h-7 mb-4 mx-auto w-fit rounded-full bg-surface2 border border-border flex items-center gap-2 px-5 animate-fadeIn">
      <span className="font-display text-subtle text-[13px] tracking-[0.08em] leading-none whitespace-nowrap">
        FINAL RESULTS ARE BEING TALLIED
      </span>
      {showingMidway && (
        <span className="font-body text-muted text-[12px] whitespace-nowrap">
          Showing midway standings in the meantime
        </span>
      )}
    </div>
  );
}
