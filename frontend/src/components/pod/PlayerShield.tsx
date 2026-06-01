import { useId, useLayoutEffect, useRef } from "react";
import { Pips } from "../ManaPips";
import { Record } from "../Record";
import { Trophy } from "../Brand";
import { cn } from "../../lib/utils";
import type { PodSeat } from "../../types/leaderboard";
import type { RoundOutcome } from "./PlayerSeatPanel";

const VIEWBOX = "0 0 100 122";
const OUTER_PATH = "M 0 0 H 100 V 60 C 100 80, 85 100, 50 122 C 15 100, 0 80, 0 60 Z";
const INNER_PATH = "M 2 2 H 98 V 60 C 98 78, 84 98, 50 119 C 16 98, 2 78, 2 60 Z";
const RING_PATH = "M 1 1 H 99 V 60 C 99 79, 84.5 99, 50 120.5 C 15.5 99, 1 79, 1 60 Z";

interface Props {
  participant: PodSeat;
  selected: boolean;
  highlighted?: boolean;
  highlightedOutcome?: RoundOutcome | null;
  onClick: () => void;
  scale?: number;
}

const REF = { w: 118, h: 144, nameMax: 20, nameMin: 11, pip: 16, rec: 22 };

export function PlayerShield({ participant, selected, highlighted = false, highlightedOutcome = null, onClick, scale = 1 }: Props) {
  const isChampion = participant.placement === 1;
  const rec = participant.record ?? "0-0";
  const wins = Number(rec.split("-")[0] || 0);
  const losses = Number(rec.split("-")[1] || 0);
  const dims = {
    w: REF.w * scale,
    h: REF.h * scale,
    nameMax: REF.nameMax * scale,
    nameMin: REF.nameMin * scale,
    pip: REF.pip * scale,
    rec: REF.rec * scale,
  };

  const uid = useId().replace(/:/g, "");
  const bezelId = `bezel-${uid}`;
  const faceId = `face-${uid}`;

  const ring = ringColor(selected, highlightedOutcome);
  const isHighlight = highlighted && !selected;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      aria-label={`Seat ${participant.seatIndex + 1}: ${participant.discordName}, ${participant.record ?? "0-0"}`}
      className={cn(
        "group relative block p-0 m-0 border-0 bg-transparent cursor-pointer outline-none",
        "transition-transform duration-300 ease-out will-change-transform",
        selected
          ? "-translate-y-2.5 scale-[1.04]"
          : "hover:-translate-y-1.5 hover:scale-[1.025]",
      )}
      style={{ width: dims.w, height: dims.h }}
    >
      <svg
        viewBox={VIEWBOX}
        preserveAspectRatio="none"
        className="absolute inset-0 w-full h-full overflow-visible"
        aria-hidden="true"
        style={{
          filter: selected
            ? "drop-shadow(0 8px 14px rgba(0, 0, 0, 0.55))"
            : "drop-shadow(0 4px 8px rgba(0, 0, 0, 0.5))",
        }}
      >
        <defs>
          <linearGradient id={bezelId} x1="0" y1="0" x2="0" y2="1">
            {selected ? (
              <>
                <stop offset="0%" stopColor="#4b556b" />
                <stop offset="30%" stopColor="#2a3142" />
                <stop offset="100%" stopColor="#1d2330" />
              </>
            ) : (
              <>
                <stop offset="0%" stopColor="#3b4458" />
                <stop offset="30%" stopColor="#2a3142" />
                <stop offset="100%" stopColor="#14181f" />
              </>
            )}
          </linearGradient>
          <linearGradient id={faceId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#181d27" />
            <stop offset="55%" stopColor="#10141c" />
            <stop offset="100%" stopColor="#06080d" />
          </linearGradient>
        </defs>
        <path d={OUTER_PATH} fill={`url(#${bezelId})`} />
        <path d={INNER_PATH} fill={`url(#${faceId})`} />

        {(selected || isHighlight) && (
          <path d={INNER_PATH} fill="none" stroke={ring} strokeWidth={2.4} strokeOpacity={1} vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      <div
        className="absolute inset-0 flex flex-col items-center"
        style={{
          paddingTop: participant.deckColors ? "16%" : "5%",
          paddingBottom: "23%",
          paddingLeft: 10,
          paddingRight: 10,
        }}
      >
        {participant.deckColors && (
          <Pips colors={participant.deckColors} size={dims.pip} />
        )}
        <div className="flex-1 flex flex-col items-center justify-center min-h-0 w-full px-1 gap-0.5">
          {isChampion && (
            <Trophy
              size={Math.round(dims.nameMax * 0.95)}
              color="#ffc63a"
              className="shrink-0"
            />
          )}
          <FitName
            text={participant.discordName}
            maxSize={dims.nameMax}
            minSize={dims.nameMin}
            className="leading-none uppercase text-text text-center"
          />
        </div>
        <div
          className="tabular-nums leading-none text-text"
          style={{
            fontSize: dims.rec,
            letterSpacing: "0.04em",
            fontFamily: "'Bebas Neue', sans-serif",
          }}
        >
          <Record wins={wins} losses={losses} mono separatorMargin={3} />
        </div>
      </div>
    </button>
  );
}

function ringColor(selected: boolean, outcome: RoundOutcome | null): string {
  const WHITE = "#e6ecf5";
  const GREEN = "#2ee85c";
  const RED = "#ff5e5e";
  const MUTED = "#7a849a";
  if (outcome == null) return WHITE;
  if (outcome === "skip" || outcome === "pending") return MUTED;
  const won = outcome === "win";
  if (selected) return won ? GREEN : RED;
  return won ? RED : GREEN;
}

function FitName({
  text,
  maxSize,
  minSize,
  className,
}: {
  text: string;
  maxSize: number;
  minSize: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const parent = el.parentElement;
    if (!parent) return;
    const canWrap = /\s/.test(text);
    const fit = () => {
      const avail = parent.clientWidth;
      if (avail <= 0) return;
      // Try to fit on a single line at max size
      el.style.whiteSpace = "nowrap";
      el.style.fontSize = `${maxSize}px`;
      if (el.scrollWidth <= avail) return;
      if (canWrap) {
        // Multi-word — allow wrap onto two lines, shrink until height fits
        el.style.whiteSpace = "normal";
        let size = maxSize;
        el.style.fontSize = `${size}px`;
        while (el.scrollHeight > size * 2.2 && size > minSize) {
          size -= 0.5;
          el.style.fontSize = `${size}px`;
        }
      } else {
        // Single word — shrink the font until it fits on one line
        let size = maxSize;
        while (el.scrollWidth > avail && size > minSize) {
          size -= 0.5;
          el.style.fontSize = `${size}px`;
        }
      }
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(parent);
    return () => ro.disconnect();
  }, [text, maxSize, minSize]);
  return (
    <span
      ref={ref}
      className={className}
      style={{
        letterSpacing: "0.02em",
        display: "inline-block",
        fontFamily: "'Bebas Neue', sans-serif",
      }}
    >
      {text}
    </span>
  );
}
