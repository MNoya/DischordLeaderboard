import React from "react";

// Single SVG donut/ring renderer. Each entry contributes a colored arc
// proportional to its `value` over the sum of all values. A neutral track sits
// underneath so partial coverage still reads as a complete circle.
//
// SVG primitives don't benefit from Tailwind utilities, so colors stay as
// explicit fills/strokes against the theme's hex palette.

const COLOR_TEXT = "#e6ecf5";
const COLOR_MUTED = "#7a8395";
const COLOR_TRACK = "#1d2330";
const COLOR_BG = "#0a0c10";

const GRADIENT_STEPS = 24;

function lerpHex(a: string, b: string, t: number): string {
  const ar = parseInt(a.slice(1, 3), 16);
  const ag = parseInt(a.slice(3, 5), 16);
  const ab = parseInt(a.slice(5, 7), 16);
  const br = parseInt(b.slice(1, 3), 16);
  const bg = parseInt(b.slice(3, 5), 16);
  const bb = parseInt(b.slice(5, 7), 16);
  const r = Math.round(ar + (br - ar) * t);
  const g = Math.round(ag + (bg - ag) * t);
  const bl = Math.round(ab + (bb - ab) * t);
  const hex = (n: number) => n.toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(bl)}`;
}

const STOP_HOLD = 0.25;

function sharpen(f: number): number {
  if (f <= STOP_HOLD) return 0;
  if (f >= 1 - STOP_HOLD) return 1;
  return (f - STOP_HOLD) / (1 - 2 * STOP_HOLD);
}

function multiStop(stops: string[], t: number): string {
  if (stops.length === 1) return stops[0];
  const segs = stops.length - 1;
  const u = Math.min(t * segs, segs);
  const i = Math.min(Math.floor(u), segs - 1);
  return lerpHex(stops[i], stops[i + 1], sharpen(u - i));
}

export interface DonutEntry {
  key: string;
  value: number;
  color?: string;
  colors?: string[];
  symbol?: React.ReactNode;
}

export function DonutChart({
  entries,
  radius = 42,
  strokeWidth = 14,
  trackColor = COLOR_TRACK,
  topLabel,
  bottomLabel,
  topFontSize,
  bottomFontSize,
  size,
  padding = 8,
  pieHole,
  defs,
  activeKey,
  onHoverEntry,
}: {
  entries: DonutEntry[];
  radius?: number;
  strokeWidth?: number;
  trackColor?: string;
  topLabel?: React.ReactNode;
  bottomLabel?: React.ReactNode;
  topFontSize?: number;
  bottomFontSize?: number;
  size?: number;
  padding?: number;
  pieHole?: number;
  defs?: React.ReactNode;
  activeKey?: string | null;
  onHoverEntry?: (key: string | null) => void;
}) {
  const isPie = pieHole != null;
  const outerR = radius + strokeWidth / 2;
  const innerR = isPie ? outerR * pieHole! : radius - strokeWidth / 2;
  const drawR = isPie ? (outerR + innerR) / 2 : radius;
  const drawSW = isPie ? outerR - innerR : strokeWidth;

  const D = size ?? outerR * 2 + padding;
  const C = 2 * Math.PI * drawR;
  const total = entries.reduce((s, e) => s + e.value, 0) || 1;
  const cx = D / 2;
  const cy = D / 2;

  const tfs = topFontSize ?? Math.round(radius * 0.5);
  const bfs = bottomFontSize ?? Math.round(radius * 0.22);

  type SliceMeta = { entry: DonutEntry; startFrac: number; endFrac: number };
  const slices: SliceMeta[] = [];
  {
    let cum = 0;
    for (const e of entries) {
      const frac = e.value / total;
      slices.push({ entry: e, startFrac: cum, endFrac: cum + frac });
      cum += frac;
    }
  }

  const SEAM_OVERLAP = 1;
  const HOVER_OFFSET = 7;

  function renderSlice(s: SliceMeta): React.ReactNode {
    const isActive = activeKey != null && activeKey === s.entry.key;
    const sliceOuter = outerR + (isActive ? HOVER_OFFSET : 0);
    const sliceDrawR = (sliceOuter + innerR) / 2;
    const sliceDrawSW = sliceOuter - innerR;
    const sliceC = 2 * Math.PI * sliceDrawR;

    const frac = s.endFrac - s.startFrac;
    const stops = (s.entry.colors && s.entry.colors.length > 0)
      ? s.entry.colors
      : [s.entry.color ?? trackColor];
    const steps = stops.length === 1 ? 1 : GRADIENT_STEPS;
    const subFrac = frac / steps;

    const subArcs: React.ReactNode[] = [];
    for (let i = 0; i < steps; i++) {
      const t = steps === 1 ? 0 : (i + 0.5) / steps;
      const color = multiStop(stops, t);
      const segLen = subFrac * sliceC + (i < steps - 1 ? SEAM_OVERLAP : 0);
      const dash = `${segLen} ${sliceC}`;
      const offset = -(s.startFrac + subFrac * i) * sliceC;
      subArcs.push(
        <circle
          key={i}
          cx={cx}
          cy={cy}
          r={sliceDrawR}
          fill="none"
          stroke={color}
          strokeWidth={sliceDrawSW}
          strokeDasharray={dash}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
      );
    }

    return (
      <g
        key={s.entry.key}
        onMouseEnter={onHoverEntry ? () => onHoverEntry(s.entry.key) : undefined}
        onMouseLeave={onHoverEntry ? () => onHoverEntry(null) : undefined}
        onPointerDown={onHoverEntry ? () => onHoverEntry(s.entry.key) : undefined}
        style={{
          cursor: onHoverEntry ? "pointer" : undefined,
          transition: "all 120ms ease-out",
        }}
      >
        {subArcs}
      </g>
    );
  }

  const nonActiveArcs = slices
    .filter((s) => activeKey !== s.entry.key)
    .map(renderSlice);
  const activeSlice = slices.find((s) => activeKey === s.entry.key);
  const activeArc = activeSlice ? renderSlice(activeSlice) : null;

  const dividers: React.ReactNode[] = [];
  if (slices.length > 1) {
    const inner = isPie ? innerR : radius - strokeWidth / 2 - 0.5;
    const outer = isPie ? outerR : radius + strokeWidth / 2 + 0.5;
    slices.forEach((s, idx) => {
      const angle = s.startFrac * 2 * Math.PI - Math.PI / 2;
      const x1 = cx + inner * Math.cos(angle);
      const y1 = cy + inner * Math.sin(angle);
      const x2 = cx + outer * Math.cos(angle);
      const y2 = cy + outer * Math.sin(angle);
      dividers.push(
        <line
          key={`div-${idx}`}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke={COLOR_BG}
          strokeWidth={1.5}
          strokeLinecap="butt"
        />
      );
    });
  }

  const symbolOverlays = slices
    .filter((s) => s.entry.symbol != null)
    .map((s) => {
      const midFrac = (s.startFrac + s.endFrac) / 2;
      const angle = midFrac * 2 * Math.PI - Math.PI / 2;
      const symbolR = isPie ? drawR : radius;
      const x = cx + symbolR * Math.cos(angle);
      const y = cy + symbolR * Math.sin(angle);
      return (
        <div
          key={`sym-${s.entry.key}`}
          style={{
            position: "absolute",
            left: x,
            top: y,
            transform: "translate(-50%, -50%)",
            pointerEvents: "none",
          }}
        >
          {s.entry.symbol}
        </div>
      );
    });

  return (
    <div className="shrink-0 relative" style={{ width: D, height: D }}>
      <svg width={D} height={D} viewBox={`0 0 ${D} ${D}`} style={{ overflow: "visible" }}>
        {defs && <defs>{defs}</defs>}
        {!isPie && (
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={trackColor}
            strokeWidth={strokeWidth}
          />
        )}
        {nonActiveArcs}
        {dividers}
        {activeArc}
        {!isPie && topLabel != null && (
          <text
            x={cx}
            y={cy}
            dy={bottomLabel != null ? -2 : Math.round(tfs / 3)}
            textAnchor="middle"
            fill={COLOR_TEXT}
            fontFamily="'Bebas Neue', sans-serif"
            fontSize={tfs}
          >
            {topLabel}
          </text>
        )}
        {!isPie && bottomLabel != null && (
          <text
            x={cx}
            y={cy}
            dy={Math.round(tfs * 0.55) + 4}
            textAnchor="middle"
            fill={COLOR_MUTED}
            fontFamily="'Bebas Neue', sans-serif"
            fontSize={bfs}
            letterSpacing="0.2em"
          >
            {bottomLabel}
          </text>
        )}
      </svg>
      {symbolOverlays}
    </div>
  );
}
