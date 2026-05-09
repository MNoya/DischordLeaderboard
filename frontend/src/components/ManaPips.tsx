// Mana symbols backed by Andrew Gioia's Mana Font (loaded from CDN in
// index.html). The font renders proper MTG mana costs (rounded swatch + glyph)
// for any color via `<i class="ms ms-{c} ms-cost ms-shadow" />`. Sized via
// font-size — `ms-cost` tracks it.
//
// Splash colors (lowercase in 17lands strings) render at ~70% size with a
// dimmed opacity so they read visibly secondary.

type Color = "W" | "U" | "B" | "R" | "G";

export function Pip({ c, size = 14 }: { c: Color; size?: number }) {
  return (
    <i
      className={`ms ms-${c.toLowerCase()} ms-cost ms-shadow shrink-0`}
      style={{ fontSize: size, lineHeight: 1 }}
      aria-label={c}
    />
  );
}

// Pips renders a horizontal stack from a 17lands-style colour string. Uppercase =
// main colour (full-size), lowercase = splash (smaller, dimmed). Order is
// preserved verbatim — no WUBRG sort here so the splash position reads true.
export function Pips({ colors, size = 12 }: { colors: string; size?: number }) {
  if (!colors) {
    // Colorless archetype — render as a single colorless mana symbol.
    return (
      <i
        className="ms ms-c ms-cost ms-shadow shrink-0"
        style={{ fontSize: size, lineHeight: 1 }}
        aria-label="C"
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
            <Pip c={upper} size={isMain ? size : Math.round(size * 0.75)} />
          </span>
        );
      })}
    </span>
  );
}
