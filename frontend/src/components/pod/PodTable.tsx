import { useLayoutEffect, useRef, useState } from "react";
import { PlayerShield } from "./PlayerShield";
import { cn } from "../../lib/utils";
import type { PodParticipant } from "../../data/fixtures/pod-sos-3";

interface Props {
  participants: PodParticipant[];
  selectedSeat: number | null;
  highlightedSeat?: number | null;
  highlightedRound?: number | null;
  highlightedWon?: boolean | null;
  onSelect: (seat: number | null) => void;
  podNumber: number;
  setCode: string;
  date: string;
  maxWidth?: number | string;
}

const ORBIT_RADIUS_PCT = 39;
const ARROW_ORBIT_PCT = 34.5;
const ARROW_OFFSET_RAD = (2 * Math.PI) / 180;
const ARROW_OFFSET_BY_INDEX: Record<number, number> = {
  1: -ARROW_OFFSET_RAD,
  6: ARROW_OFFSET_RAD,
};
const SHIELD_REF_WIDTH = 640;

export function PodTable({
  participants,
  selectedSeat,
  highlightedSeat = null,
  highlightedRound = null,
  highlightedWon = null,
  onSelect,
  podNumber,
  setCode,
  date,
  maxWidth = 720,
}: Props) {
  const sorted = [...participants].sort((a, b) => a.seatIndex - b.seatIndex);
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      if (w > 0) setScale(w / SHIELD_REF_WIDTH);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      className="relative mx-auto w-full transition-[max-width] duration-500 ease-out"
      style={{ maxWidth, aspectRatio: "1 / 1", containerType: "inline-size" }}
    >
      <div className="absolute inset-[15%] overflow-hidden rounded-full">
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(circle at 50% 38%, #232a3a 0%, #181d28 28%, #10141c 58%, #070a0f 100%)",
          }}
        />
        <div
          className="absolute inset-0 pointer-events-none mix-blend-overlay opacity-[0.18]"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='240' height='240' filter='url(%23n)'/></svg>\")",
          }}
        />
        <div
          className="absolute inset-0 pointer-events-none rounded-full"
          style={{
            boxShadow:
              "inset 0 0 0 1px #2a3142, inset 0 0 0 5px #0a0c10, inset 0 0 0 6px #2a3142, inset 0 60px 90px -40px rgba(0,0,0,0.85), inset 0 -60px 90px -40px rgba(0,0,0,0.85)",
          }}
        />
      </div>

      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <CenterMedallion podNumber={podNumber} setCode={setCode} date={date} />
      </div>

      <PassDirectionArrows seatCount={sorted.length} />

      {selectedSeat != null && highlightedSeat != null && selectedSeat !== highlightedSeat && (
        <PairingLine
          fromSeat={selectedSeat}
          toSeat={highlightedSeat}
          seatCount={sorted.length}
          round={highlightedRound}
          won={highlightedWon}
        />
      )}

      {sorted.map((p) => {
        const angle = (p.seatIndex / sorted.length) * Math.PI * 2 - Math.PI / 2;
        const x = 50 + Math.cos(angle) * ORBIT_RADIUS_PCT;
        const y = 50 + Math.sin(angle) * ORBIT_RADIUS_PCT;
        const isSelected = selectedSeat === p.seatIndex;
        return (
          <div
            key={p.playerId}
            className="absolute"
            style={{
              left: `${x}%`,
              top: `${y}%`,
              transform: "translate(-50%, -50%)",
            }}
          >
            <PlayerShield
              participant={p}
              selected={isSelected}
              highlighted={!isSelected && highlightedSeat === p.seatIndex}
              highlightedWon={highlightedWon}
              onClick={() => onSelect(isSelected ? null : p.seatIndex)}
              scale={scale}
            />
          </div>
        );
      })}
    </div>
  );
}

function PairingLine({
  fromSeat,
  toSeat,
  seatCount,
  round,
  won,
}: {
  fromSeat: number;
  toSeat: number;
  seatCount: number;
  round: number | null;
  won: boolean | null;
}) {
  const project = (s: number) => {
    const a = (s / seatCount) * Math.PI * 2 - Math.PI / 2;
    return {
      x: 50 + Math.cos(a) * ORBIT_RADIUS_PCT,
      y: 50 + Math.sin(a) * ORBIT_RADIUS_PCT,
    };
  };
  const a = project(fromSeat);
  const b = project(toSeat);
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  const isLoss = won === false;
  const tone = isLoss ? "text-red" : "text-green";
  const pillBorder = isLoss ? "border-red/60" : "border-green/60";
  return (
    <>
      <svg
        className={cn("absolute inset-0 w-full h-full pointer-events-none", tone)}
        viewBox="0 0 100 100"
        aria-hidden="true"
      >
        <line
          x1={a.x}
          y1={a.y}
          x2={b.x}
          y2={b.y}
          stroke="currentColor"
          strokeOpacity="0.22"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        <line
          x1={a.x}
          y1={a.y}
          x2={b.x}
          y2={b.y}
          stroke="currentColor"
          strokeOpacity="0.95"
          strokeWidth="0.55"
          strokeLinecap="round"
        />
      </svg>
      {round != null && (
        <div
          className={cn(
            "absolute pointer-events-none font-display bg-bg border leading-none",
            tone,
            pillBorder,
          )}
          style={{
            left: `${mid.x}%`,
            top: `${mid.y}%`,
            transform: "translate(-50%, -50%)",
            padding: "0.55cqw 0.9cqw",
            fontSize: "2.2cqw",
            letterSpacing: "0.18em",
            zIndex: 20,
          }}
        >
          R{round}
        </div>
      )}
    </>
  );
}

function PassDirectionArrows({ seatCount }: { seatCount: number }) {
  return (
    <>
      {Array.from({ length: seatCount }, (_, i) => {
        const midAngle = ((i + 0.5) / seatCount) * Math.PI * 2 - Math.PI / 2 + (ARROW_OFFSET_BY_INDEX[i] ?? 0);
        const x = 50 + Math.cos(midAngle) * ARROW_ORBIT_PCT;
        const y = 50 + Math.sin(midAngle) * ARROW_ORBIT_PCT;
        const tangentDeg = (midAngle * 180) / Math.PI + 90;
        return (
          <div
            key={i}
            className="absolute pointer-events-none"
            style={{
              left: `${x}%`,
              top: `${y}%`,
              width: "3.2cqw",
              height: "3.2cqw",
              transform: `translate(-50%, -50%) rotate(${tangentDeg}deg)`,
            }}
          >
            <svg viewBox="0 0 24 24" className="w-full h-full" aria-hidden="true">
              <path
                d="M 4 7 L 11 12 L 4 17 M 13 7 L 20 12 L 13 17"
                fill="none"
                stroke="#c4ccdb"
                strokeOpacity="0.75"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          </div>
        );
      })}
    </>
  );
}

function CenterMedallion({ podNumber, setCode, date }: { podNumber: number; setCode: string; date: string }) {
  const dateLabel = formatDate(date);
  return (
    <div
      className="flex flex-col items-center justify-center text-center select-none"
      style={{ gap: "2.2cqw" }}
    >
      <div
        className="font-display text-text leading-none"
        style={{ fontSize: "11cqw", letterSpacing: "0.02em" }}
      >
        POD <span className="text-green">#{podNumber}</span>
      </div>
      <div className="flex items-center" style={{ gap: "2.2cqw" }}>
        <i
          className={`ss ss-${setCode.toLowerCase()} text-white`}
          style={{ fontSize: "8cqw", lineHeight: 1 }}
          aria-hidden="true"
        />
        <span
          className="font-display text-text"
          style={{ fontSize: "5.2cqw", letterSpacing: "0.24em" }}
        >
          {setCode}
        </span>
      </div>
      <div
        className="font-display text-muted"
        style={{ fontSize: "2.2cqw", letterSpacing: "0.32em" }}
      >
        {dateLabel}
      </div>
    </div>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  const weekday = d.toLocaleString("en-US", { weekday: "short", timeZone: "UTC" }).toUpperCase();
  const month = d.toLocaleString("en-US", { month: "long", timeZone: "UTC" }).toUpperCase();
  return `${weekday} · ${month} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}
