// Mana pip — single colored disc with a letter, matching MTG's W/U/B/R/G colour
// identity. Inline styles drive per-color fills since the palette is data-bound,
// not theme-bound.

type Color = "W" | "U" | "B" | "R" | "G";

const PIP_FILL: Record<Color, string> = {
  W: "#f8f1d8",
  U: "#7cb6e8",
  B: "#3a3537",
  R: "#e85c5c",
  G: "#5fb56e",
};

const PIP_STROKE: Record<Color, string> = {
  W: "#c9bf94",
  U: "#3d7ec0",
  B: "#1a1718",
  R: "#a83737",
  G: "#3a8048",
};

const PIP_TEXT: Record<Color, string> = {
  W: "#3a3024",
  U: "#0e2640",
  B: "#e6e0d2",
  R: "#fff",
  G: "#0e3018",
};

export function Pip({ c, size = 14 }: { c: Color; size?: number }) {
  return (
    <span
      className="inline-flex items-center justify-center rounded-full font-mono font-bold shrink-0 leading-none"
      style={{
        width: size,
        height: size,
        background: PIP_FILL[c],
        color: PIP_TEXT[c],
        border: `1px solid ${PIP_STROKE[c]}`,
        fontSize: Math.round(size * 0.62),
      }}
      aria-label={c}
    >
      {c === "B" ? "" : c}
    </span>
  );
}

// Pips renders a horizontal stack from a 17lands-style colour string. Uppercase =
// main colour (full-size), lowercase = splash (smaller, dimmed). Order is
// preserved verbatim — no WUBRG sort here so the splash position reads true.
export function Pips({ colors, size = 12 }: { colors: string; size?: number }) {
  if (!colors) {
    return (
      <span
        className="inline-block rounded-full bg-surface2 border border-border2"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span className="inline-flex gap-px items-center">
      {[...colors].map((ch, i) => {
        const isMain = ch === ch.toUpperCase();
        const upper = ch.toUpperCase() as Color;
        return (
          <span key={`${ch}-${i}`} style={{ opacity: isMain ? 1 : 0.55 }}>
            <Pip c={upper} size={isMain ? size : Math.round(size * 0.7)} />
          </span>
        );
      })}
    </span>
  );
}
