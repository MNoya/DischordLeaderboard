import { Container } from "./Container";
import { CtaPill } from "./CtaPill";
import { SectionLabel } from "./SectionLabel";
import { DiscordIcon } from "./BrandIcons";
import { SITE_LINKS } from "../data/site";

// The "join the Discord" call-to-action band, shared by the home page and the
// community page so the pitch and stats stay identical in both places.
export function DiscordBand() {
  return (
    <section
      className="border-y border-border"
      style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
    >
      <Container className="py-10 md:py-14 flex flex-col gap-6 md:flex-row md:items-center md:gap-12">
        <div className="flex-1">
          <SectionLabel letterSpacing="0.28em">PRIMARY HANGOUT</SectionLabel>
          <h2 className="font-display text-text text-[30px] md:text-[40px] leading-[1.05] tracking-[0.01em] mt-2">
            The Limited Level-Ups <span className="text-green">Discord</span>
          </h2>
          <p className="text-subtle text-[14px] md:text-[15px] leading-[1.6] max-w-[560px] mt-3">
            Where the community lives. Format-of-the-week channels, draft debriefs, pick-order polls,
            deck-check requests, and the hosts popping in between episodes.
          </p>
          <div className="mono text-[11px] tracking-[0.14em] text-muted mt-4">
            4,200+ MEMBERS · 14 CHANNELS · NEW-SET CHANNELS ON RELEASE WEEK
          </div>
        </div>
        <a href={SITE_LINKS.discord} target="_blank" rel="noreferrer" className="no-underline shrink-0">
          <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
            JOIN THE DISCHORD
          </CtaPill>
        </a>
      </Container>
    </section>
  );
}
