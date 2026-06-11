import type { ReactNode } from "react";
import { cn } from "../lib/utils";

// Standard centred content column for the community site sections.
export function Container({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-[1120px] px-5 md:px-10", className)}>{children}</div>;
}
