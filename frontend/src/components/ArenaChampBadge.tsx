const ARENA_CHAMPIONSHIP_FORMAT = "Qualifier_D2_Sealed";

export function isArenaChampionshipFormat(format: string): boolean {
  return format === ARENA_CHAMPIONSHIP_FORMAT;
}

export function ArenaChampBadge({
  size = 16,
  box,
  className,
}: {
  size?: number;
  box?: number;
  className?: string;
}) {
  const base = "inline-flex items-center justify-center shrink-0";
  return (
    <span className={className ? `${base} ${className}` : base} style={{ height: box ?? size }}>
      <img
        src={`${import.meta.env.BASE_URL}arenachamp.png`}
        alt="Arena Championship qualification"
        title="Arena Championship qualification"
        style={{ height: size, width: "auto", maxWidth: "none" }}
      />
    </span>
  );
}
