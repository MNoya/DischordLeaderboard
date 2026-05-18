type Size = "sm" | "md" | "lg";

const CHAMFER = "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)";

const SIZES: Record<Size, { fontSize: number; px: number; outer: number; inner: number }> = {
  sm: { fontSize: 14, px: 10, outer: 26, inner: 24 },
  md: { fontSize: 22, px: 14, outer: 38, inner: 36 },
  lg: { fontSize: 26, px: 18, outer: 46, inner: 44 },
};

export function RankBadge({ rank, size = "md" }: { rank: number; size?: Size }) {
  const dims = SIZES[size];
  return (
    <span
      className="inline-block font-display tracking-[0.18em]"
      style={{
        clipPath: CHAMFER,
        background: "#2ee85c",
        padding: 1,
        minHeight: dims.outer,
      }}
    >
      <span
        className="flex items-center bg-surface text-green font-display tracking-[0.06em] leading-none h-full"
        style={{
          clipPath: CHAMFER,
          minHeight: dims.inner,
          fontSize: dims.fontSize,
          paddingLeft: dims.px,
          paddingRight: dims.px,
        }}
      >
        #{rank}
      </span>
    </span>
  );
}
