// Mana symbols backed by Andrew Gioia's Mana Font (loaded from CDN in
// index.html). The font renders proper MTG mana costs (rounded swatch + glyph)
// for any color via `<i class="ms ms-{c} ms-cost ms-shadow" />`. Sized via
// font-size — `ms-cost` tracks it.
//
// Splash colors (lowercase in 17lands strings) render at ~70% size so they
// read visibly secondary while keeping full color saturation.

type Color = "W" | "U" | "B" | "R" | "G";

export function Pip({ c, size = 14 }: { c: Color; size?: number }) {
  return (
    <i
      className={`ms ms-${c.toLowerCase()} ms-cost ms-shadow shrink-0`}
      style={{ fontSize: size, letterSpacing: 0 }}
      aria-label={c}
    />
  );
}

// Pips renders a horizontal stack from a 17lands-style colour string. Uppercase =
// main colour (full-size), lowercase = splash (smaller). Order is preserved
// verbatim — no WUBRG sort here so the splash position reads true.
export function Pips({ colors, size = 12, flat = false }: { colors: string; size?: number; flat?: boolean }) {
  if (!colors) {
    return (
      <i
        className="ms ms-c ms-cost ms-shadow shrink-0"
        style={{ fontSize: size, letterSpacing: 0 }}
        aria-label="C"
      />
    );
  }
  const chars = [...colors];
  const allMain = chars.every((c) => c === c.toUpperCase());
  if (chars.length === 4 && allMain && !flat) {
    return (
      <span className="inline-grid grid-cols-2 gap-px shrink-0">
        {chars.map((ch, i) => (
          <Pip key={`${ch}-${i}`} c={ch.toUpperCase() as Color} size={size} />
        ))}
      </span>
    );
  }
  return (
    <span className="inline-flex gap-px items-center">
      {chars.map((ch, i) => {
        const isMain = ch === ch.toUpperCase();
        const upper = ch.toUpperCase() as Color;
        return (
          <Pip
            key={`${ch}-${i}`}
            c={upper}
            size={isMain ? size : Math.round(size * 0.75)}
          />
        );
      })}
    </span>
  );
}
