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

export interface DonutEntry {
  key: string;
  value: number;
  color: string;
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
}) {
  const D = size ?? radius * 2 + strokeWidth + padding;
  const C = 2 * Math.PI * radius;
  const total = entries.reduce((s, e) => s + e.value, 0) || 1;
  const cx = D / 2;
  const cy = D / 2;

  const tfs = topFontSize ?? Math.round(radius * 0.5);
  const bfs = bottomFontSize ?? Math.round(radius * 0.22);

  let cum = 0;

  return (
    <svg width={D} height={D} viewBox={`0 0 ${D} ${D}`} className="shrink-0">
      <circle cx={cx} cy={cy} r={radius} fill="none" stroke={trackColor} strokeWidth={strokeWidth} />
      {entries.map((e) => {
        const frac = e.value / total;
        const dash = `${frac * C} ${C}`;
        const offset = -cum * C;
        cum += frac;
        return (
          <circle
            key={e.key}
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={e.color}
            strokeWidth={strokeWidth}
            strokeDasharray={dash}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        );
      })}
      {topLabel != null && (
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
      {bottomLabel != null && (
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
  );
}
