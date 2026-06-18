export function P0P1Countdown({
  deadline,
  scoringDate,
  size = 13,
}: {
  deadline: Date;
  scoringDate?: Date;
  size?: number;
}) {
  const now = Date.now();
  const deadlineDiff = deadline.getTime() - now;

  if (deadlineDiff > 0) {
    const days = Math.floor(deadlineDiff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((deadlineDiff / (1000 * 60 * 60)) % 24);
    return (
      <span className="whitespace-nowrap" style={{ fontSize: size }}>
        <span className="text-muted">Closes in </span>
        <span className="text-green">
          {days} days, {hours} hours
        </span>
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
              ? `${days * 24 + hours} hours`
              : `${days} days, ${hours} hours`}
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
