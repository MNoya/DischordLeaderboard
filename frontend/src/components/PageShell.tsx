import type { ReactNode } from "react";
import { AppHeader } from "./AppHeader";
import { SiteFooter } from "./SiteFooter";

// Standard community-site page frame: themed header, a growing main, and the
// shared footer. Sections own their own width via <Container>, so main stays
// full-bleed to let the hero and bands run edge to edge.
export function PageShell({ subtitle, children }: { subtitle?: string; children: ReactNode }) {
  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle={subtitle} />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}
