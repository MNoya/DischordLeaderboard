import { useEffect, useState } from "react";
import { p0p1Now } from "../../data/p0p1DevState";

export function pluralizeUnit(value: number, unit: string) {
  return `${value} ${unit}${value === 1 ? "" : "s"}`;
}

export function formatRemaining(diff: number): string {
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  const minutes = Math.floor((diff / (1000 * 60)) % 60);
  if (days > 0) {
    return `${pluralizeUnit(days, "day")}, ${pluralizeUnit(hours, "hour")}`;
  }
  if (hours > 0) {
    return `${pluralizeUnit(hours, "hour")}, ${pluralizeUnit(minutes, "minute")}`;
  }
  return pluralizeUnit(minutes, "minute");
}

export function useTick(intervalMs: number) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}

export function P0P1Countdown({
  deadline,
  scoringDate,
  size = 13,
  pastDeadline = false,
}: {
  deadline: Date;
  scoringDate?: Date;
  size?: number;
  pastDeadline?: boolean;
}) {
  useTick(30_000);
  const now = p0p1Now();
  const deadlineDiff = deadline.getTime() - now;

  if (!pastDeadline && deadlineDiff > 0) {
    return (
      <span className="whitespace-nowrap" style={{ fontSize: size }}>
        <span className="text-muted">Closes in </span>
        <span className="text-green">{formatRemaining(deadlineDiff)}</span>
      </span>
    );
  }

  if (scoringDate) {
    const scoringDiff = scoringDate.getTime() - now;
    if (scoringDiff > 0) {
      const days = Math.floor(scoringDiff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((scoringDiff / (1000 * 60 * 60)) % 24);
      const showHours = days < 2;
      return (
        <span className="whitespace-nowrap" style={{ fontSize: size }}>
          <span className="text-muted">Results in </span>
          <span className="text-green">
            {showHours
              ? pluralizeUnit(days * 24 + hours, "hour")
              : `${pluralizeUnit(days, "day")}, ${pluralizeUnit(hours, "hour")}`}
          </span>
        </span>
      );
    }
    return (
      <span className="text-green" style={{ fontSize: size }}>
        Results are in
      </span>
    );
  }

  return (
    <span className="text-muted" style={{ fontSize: size }}>
      Entries have closed
    </span>
  );
}
