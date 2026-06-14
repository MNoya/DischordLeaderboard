// Mana symbols backed by Andrew Gioia's Mana Font (loaded from CDN in
// index.html). Sized via font-size — `ms-cost` tracks it.

type Color = "W" | "U" | "B" | "R" | "G";

// ManaCost is used for rendering the mana cost of a card, based on the {W}{U}{2} style cost string from Scryfall.
export function ManaCost({ cost, size = 14 }: { cost: string; size?: number }) {
  const symbols = [...cost.matchAll(/\{([^}]+)\}/g)].map((m) => m[1]);
  if (symbols.length === 0) return <span>—</span>;
  return (
    <span className="inline-flex gap-px items-center">
      {symbols.map((s, i) => (
        <i
          key={i}
          // replace is for hybrid mana symbols
          className={`ms ms-${s.replace("/", "").toLowerCase()} ms-cost ms-shadow shrink-0`}
          style={{ fontSize: size, letterSpacing: 0 }}
          aria-label={s}
        />
      ))}
    </span>
  );
}

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
