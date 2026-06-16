// Status chip that takes the hero's CTA slot once the user is logged in. It
// rhymes with CtaPill's chamfer geometry but inverts the intent: a calm dark
// confirmation instead of a green call-to-action. The check draws itself in on
// mount, then rests — reassurance reads as "done", not "in progress".
//
// Once all eight slots are filled it promotes to a "vote ready" state: the check
// disc fills solid and the copy confirms the entry is in, while keeping the
// auto-saved fact in the sub-line.
//
// The hairline border is the leaderboard SetChip technique: clip-path can't
// carry a real border across the chamfered corners, so a 1px border2 layer sits
// behind the surface panel and shows through as the edge.

const CHAMFER = "polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)";

export function AutoSaveBadge({ complete = false }: { complete?: boolean }) {
  const title = complete ? "PICKS SAVED" : "AUTO-SAVED";
  const subtitle = complete ? "Edit anytime before the deadline" : "Synced to your account as you pick";

  return (
    <div
      className="inline-block animate-fadeUpIn"
      style={{ clipPath: CHAMFER, background: "#3b4458", padding: 1 }}
    >
      <div
        className="flex items-center gap-3.5 bg-surface2 py-2.5 pl-5 pr-5"
        style={{ clipPath: CHAMFER }}
      >
        <span
          className={`relative inline-flex h-9 w-9 items-center justify-center rounded-full ${
            complete ? "bg-green" : "bg-green/15"
          }`}
        >
          {!complete && <span className="absolute inset-0 rounded-full ring-1 ring-inset ring-green/40" />}
          <svg key={String(complete)} width="18" height="18" viewBox="0 0 24 24" fill="none" className="relative">
            <path
              d="M5 12.5 L10 17.5 L19 7"
              stroke={complete ? "#0a0c10" : "#2ee85c"}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="animate-drawCheck"
              style={{ strokeDasharray: 24 }}
            />
          </svg>
        </span>
        <span className="grid">
          <span aria-hidden className="invisible col-start-1 row-start-1 flex flex-col gap-1 leading-none">
            <span className="font-display text-[17px] tracking-[0.14em]">AUTO-SAVED</span>
            <span className="font-body text-[12px]">Synced to your account as you pick</span>
          </span>
          <span className="col-start-1 row-start-1 flex flex-col gap-1 leading-none">
            <span className="font-display text-[17px] tracking-[0.14em] text-green">{title}</span>
            <span className="font-body text-[12px] text-muted">{subtitle}</span>
          </span>
        </span>
      </div>
    </div>
  );
}
