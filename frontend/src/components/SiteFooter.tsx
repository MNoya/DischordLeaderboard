import { Container } from "./Container";
import { LISTEN_ON, SITE_LINKS } from "../data/site";

export function SiteFooter() {
  return (
    <footer className="border-t border-border mt-16 md:mt-24">
      <Container className="py-6 flex flex-col-reverse md:flex-row items-center justify-between gap-3 text-[11px] md:text-[12px] text-muted">
        <span className="mono text-center md:text-left">
          © Limited Level-Ups · Not affiliated with Wizards of the Coast
        </span>
        <nav className="flex items-center gap-4 font-display tracking-[0.12em] text-[13px]">
          {LISTEN_ON.map((l) => (
            <a key={l.label} href={l.url} target="_blank" rel="noreferrer" className="no-underline hover:text-green transition-colors">
              {l.label}
            </a>
          ))}
          <a href={SITE_LINKS.patreon} target="_blank" rel="noreferrer" className="no-underline hover:text-green transition-colors">
            Patreon
          </a>
        </nav>
      </Container>
    </footer>
  );
}
