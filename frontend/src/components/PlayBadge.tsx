import type { ReactNode } from "react";

export function PlayBadge({ children }: { children: ReactNode }) {
  return (
    <span className="flex h-16 w-16 items-center justify-center rounded-full bg-green/70 text-white">
      {children}
    </span>
  );
}
