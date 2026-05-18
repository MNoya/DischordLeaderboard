import type { CSSProperties, ReactNode } from "react";
import { cn } from "../lib/utils";

export function HeroSection({
  className,
  style,
  children,
}: {
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}) {
  return (
    <section
      className={cn("border-b border-border", className)}
      style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)", ...style }}
    >
      {children}
    </section>
  );
}
