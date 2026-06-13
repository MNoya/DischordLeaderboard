import type { IconType } from "react-icons";
import { SiApplepodcasts, SiPatreon, SiRss, SiSpotify, SiYoutube } from "react-icons/si";
import { Container } from "./Container";
import { LISTEN_ON, SITE_LINKS } from "../data/site";
import { cn } from "../lib/utils";

const FOOTER_ICONS: Record<string, IconType> = {
  Apple: SiApplepodcasts,
  Spotify: SiSpotify,
  YouTube: SiYoutube,
  RSS: SiRss,
  Patreon: SiPatreon,
};

// `flush` drops the top margin so the footer can sit directly under a
// viewport-filling dashboard instead of pushing it up.
export function SiteFooter({ flush = false }: { flush?: boolean }) {
  const links = [...LISTEN_ON, { label: "Patreon", url: SITE_LINKS.patreon }];
  const row = (
    <div className="flex flex-col-reverse gap-3 text-[11px] md:text-[12px] text-muted md:flex-row md:items-center md:justify-between">
      <span className="mono block text-center text-[10px] leading-tight md:flex md:flex-col md:gap-0.5 md:text-left">
        <span>© Limited Level-Ups is unofficial Fan Content permitted under the Fan Content Policy.</span>{" "}
        <span>Not approved or endorsed by Wizards. Portions © Wizards of the Coast.</span>
      </span>
      <nav className="flex items-center justify-center gap-4 font-display tracking-[0.12em] text-[13px] md:justify-end">
        {links.map(({ label, url }) => {
          const Icon = FOOTER_ICONS[label];
          return (
            <a
              key={label}
              href={url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 no-underline hover:text-green transition-colors"
            >
              {Icon ? <Icon className="text-[14px]" /> : null}
              {label}
            </a>
          );
        })}
      </nav>
    </div>
  );
  return (
    <footer className={cn("border-t border-border", flush ? "" : "mt-16 md:mt-24")}>
      {flush ? <div className="px-4 lg:px-5 py-3">{row}</div> : <Container className="py-6">{row}</Container>}
    </footer>
  );
}
