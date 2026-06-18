import type { ReactNode } from "react";
import { cn } from "../lib/utils";

// Standard content column for the community site sections. Runs near full-width like the rest
// of the app (leaderboard, home, p0p1) with a high cap so it doesn't stretch on ultrawide;
// prose inside still caps its own measure for readability.
export function Container({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-[1760px] px-4 sm:px-6 lg:px-10", className)}>{children}</div>;
}
