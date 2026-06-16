export function P0P1Countdown({ deadline, size = 13 }: { deadline: Date; size?: number }) {
  const diff = deadline.getTime() - Date.now();
  if (diff <= 0) {
    return (
      <span className="text-muted" style={{ fontSize: size }}>
        Entries have closed
      </span>
    );
  }
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  return (
    <span className="whitespace-nowrap" style={{ fontSize: size }}>
      <span className="text-muted">Closes in </span>
      <span className="text-green">
        {days} days, {hours} hours
      </span>
    </span>
  );
}
