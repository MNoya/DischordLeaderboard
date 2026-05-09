// Filter dropdown — used twice on the leaderboard (FORMAT + ARCHETYPE) and on
// the player profile draft log. Native <select> sits invisibly on top of a
// styled wrapper so the visual tracks the design exactly while keeping a11y /
// mobile native scrollers for free.

export function FilterDropdown({
  label,
  value,
  options,
  onChange,
  variant = "desktop",
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (next: string) => void;
  variant?: "desktop" | "mobile";
}) {
  const isMobile = variant === "mobile";
  return (
    <label
      className={
        isMobile
          ? "relative flex flex-1 items-center gap-2 px-2.5 py-1 min-w-0 bg-transparent border border-border2 text-text font-display text-[11px] tracking-[0.16em] cursor-pointer"
          : "relative flex items-center gap-2 px-3.5 py-1.5 min-w-[220px] bg-transparent border border-border2 text-text font-display text-[13px] tracking-[0.14em] cursor-pointer"
      }
    >
      <span
        className={
          isMobile
            ? "text-muted text-[9px] tracking-[0.22em]"
            : "text-muted text-[11px] tracking-[0.22em]"
        }
      >
        {label}
      </span>
      <span>{(options.find((o) => o.value === value) ?? options[0]).label}</span>
      <span className="flex-1" />
      <span className={isMobile ? "text-muted text-[9px]" : "text-muted text-[10px]"}>▾</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer appearance-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
