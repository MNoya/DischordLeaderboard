import { Fragment, useLayoutEffect, useRef, useState } from "react";
import { Pips } from "../ManaPips";
import { Record } from "../Record";
import { cn } from "../../lib/utils";
import { HeroSection } from "../HeroSection";
import { PlayerSeatPanel } from "./PlayerSeatPanel";
import type { PodMatch, PodParticipant, PodReplayRow } from "../../data/fixtures/pod-sos-3";

interface Props {
  participants: PodParticipant[];
  participantsBySeatName: Map<string, PodParticipant>;
  matches: PodMatch[];
  replays: PodReplayRow[];
  selectedSeat: number | null;
  onSelect: (seat: number | null) => void;
  podNumber: number;
  setCode: string;
}

const GRID_REF_WIDTH = 380;
const GRID_MAX_WIDTH = 560;
const REF_TILE = { w: 74, h: 64 };
const REF_ARROW = 16;

export function MobileSeatStack({
  participants,
  participantsBySeatName,
  matches,
  replays,
  selectedSeat,
  onSelect,
  podNumber,
  setCode,
}: Props) {
  const sorted = [...participants].sort((a, b) => a.seatIndex - b.seatIndex);
  const selected = selectedSeat == null
    ? null
    : participants.find((p) => p.seatIndex === selectedSeat) ?? null;

  return (
    <div className="flex flex-col">
      <HeroSection className="px-[18px] pt-5 pb-5">
        <TileGrid
          participants={sorted}
          selectedSeat={selectedSeat}
          onSelect={onSelect}
          podNumber={podNumber}
          setCode={setCode}
        />
      </HeroSection>

      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out"
        style={{ gridTemplateRows: selected ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          {selected && (
            <div className="bg-surface">
              <PlayerSeatPanel
                key={selected.playerId}
                participant={selected}
                participantsBySeatName={participantsBySeatName}
                matches={matches}
                replays={replays}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TileGrid({
  participants,
  selectedSeat,
  onSelect,
  podNumber,
  setCode,
}: {
  participants: PodParticipant[];
  selectedSeat: number | null;
  onSelect: (seat: number | null) => void;
  podNumber: number;
  setCode: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      if (w > 0) setScale(w / GRID_REF_WIDTH);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = participants.length;
  const cols = Math.ceil(n / 2);
  const topRow = participants.slice(0, cols);
  const bottomRow = participants.slice(cols).reverse();
  const tileW = REF_TILE.w * scale;

  return (
    <div
      ref={ref}
      className="w-full mx-auto"
      style={{ maxWidth: GRID_MAX_WIDTH }}
    >
      <TileRow
        tiles={topRow}
        arrowDir="right"
        selectedSeat={selectedSeat}
        onSelect={onSelect}
        scale={scale}
      />
      <div
        className="flex items-center justify-between gap-2"
        style={{ paddingTop: 10 * scale, paddingBottom: 10 * scale }}
      >
        <div style={{ width: tileW, display: "flex", justifyContent: "center" }}>
          <PassChevron direction="up" scale={scale} />
        </div>
        <div
          className="flex items-center text-muted font-display"
          style={{
            gap: 8 * scale,
            fontSize: Math.round(18 * scale),
          }}
        >
          <span>
            POD <span className="text-text">#{podNumber}</span>
          </span>
          <i
            className={`ss ss-${setCode.toLowerCase()} text-text`}
            style={{ fontSize: Math.round(22 * scale), lineHeight: 1 }}
            aria-hidden="true"
          />
          <span className="text-text">{setCode}</span>
        </div>
        <div style={{ width: tileW, display: "flex", justifyContent: "center" }}>
          <PassChevron direction="down" scale={scale} />
        </div>
      </div>
      <TileRow
        tiles={bottomRow}
        arrowDir="left"
        selectedSeat={selectedSeat}
        onSelect={onSelect}
        scale={scale}
      />
    </div>
  );
}

function TileRow({
  tiles,
  arrowDir,
  selectedSeat,
  onSelect,
  scale,
}: {
  tiles: PodParticipant[];
  arrowDir: "right" | "left";
  selectedSeat: number | null;
  onSelect: (seat: number | null) => void;
  scale: number;
}) {
  return (
    <div className="flex items-center justify-between">
      {tiles.map((p, i) => (
        <Fragment key={p.playerId}>
          <PlayerTile
            participant={p}
            selected={selectedSeat === p.seatIndex}
            onClick={() => onSelect(p.seatIndex)}
            scale={scale}
          />
          {i < tiles.length - 1 && <PassChevron direction={arrowDir} scale={scale} />}
        </Fragment>
      ))}
    </div>
  );
}

function PassChevron({
  direction,
  scale,
}: {
  direction: "right" | "left" | "up" | "down";
  scale: number;
}) {
  const rotation =
    direction === "right" ? 0 : direction === "down" ? 90 : direction === "left" ? 180 : 270;
  const size = REF_ARROW * scale;
  return (
    <div
      className="pointer-events-none"
      style={{
        width: size,
        height: size,
        transform: `rotate(${rotation}deg)`,
      }}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" className="w-full h-full">
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
}

function PlayerTile({
  participant,
  selected,
  onClick,
  scale,
}: {
  participant: PodParticipant;
  selected: boolean;
  onClick: () => void;
  scale: number;
}) {
  const isChampion = participant.placement === 1;
  const wins = Number(participant.record.split("-")[0]);
  const losses = Number(participant.record.split("-")[1]);
  const w = REF_TILE.w * scale;
  const h = REF_TILE.h * scale;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      aria-label={`Seat ${participant.seatIndex + 1}: ${participant.displayName}, ${participant.record}`}
      className={cn(
        "block p-0 m-0 bg-surface border transition-colors text-left",
        selected
          ? "border-green bg-surface2"
          : isChampion
            ? "border-border2"
            : "border-border hover:border-border2",
      )}
      style={{
        width: w,
        height: h,
        boxShadow: selected ? "0 0 12px -2px rgba(46, 232, 92, 0.35)" : undefined,
      }}
    >
      <div className="h-full flex flex-col items-center justify-between" style={{ paddingTop: 5 * scale, paddingBottom: 5 * scale }}>
        <Pips colors={participant.deckColors} size={Math.round(10 * scale)} />
        <div
          className={cn(
            "font-display leading-none uppercase truncate w-full text-center px-1",
            isChampion ? "text-green" : "text-text",
          )}
          style={{
            fontSize: Math.round(12 * scale),
            letterSpacing: "0.02em",
            fontFamily: "'Bebas Neue', sans-serif",
          }}
        >
          {participant.displayName}
        </div>
        <div
          className="tabular-nums leading-none text-text"
          style={{
            fontSize: Math.round(12 * scale),
            letterSpacing: "0.06em",
            fontFamily: "'Bebas Neue', sans-serif",
          }}
        >
          <Record wins={wins} losses={losses} mono separatorMargin={2} />
        </div>
      </div>
    </button>
  );
}
