import type { ReactNode } from "react";
import { PageShell } from "../components/PageShell";
import { Container } from "../components/Container";
import { DiscordBand } from "../components/DiscordBand";
import { HostCard } from "../components/HostCard";
import { PlatformCard } from "../components/PlatformCard";
import { ArrowRight } from "../components/Icons";
import { COMMUNITY_PLATFORMS, SHOW_FORMAT, SITE_LINKS } from "../data/site";

export function CommunityPage() {
  return (
    <PageShell subtitle="COMMUNITY">
      <DiscordBand />

      <Container className="pt-12 md:pt-16">
        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-8 lg:gap-12 items-start">
          <div>
            <Heading>About the show</Heading>
            <div className="flex flex-col gap-4 text-muted text-[14px] md:text-[15px] leading-[1.7]">
              <p>
                <span className="text-text">Limited Level-Ups</span> is a weekly podcast dedicated to helping players
                improve at Magic: the Gathering's draft and sealed formats. Every new set gets a Primer on release week,
                followed by a deeper Set Review, draft-along episodes with guests, and a Sunset episode to close out the
                format. We also run Strategy episodes on evergreen topics — reading signals, pivoting archetypes,
                mulligan decisions — and a regular listener Mailbag.
              </p>
              <p>
                The show started in November 2020. Five years and 240+ episodes later, it's Alex going deep on whatever
                format is live — with occasional guests for draft-alongs.
              </p>
            </div>
          </div>
          <div className="aspect-square w-full border border-border bg-surface flex items-center justify-center mono text-[11px] tracking-[0.18em] text-dim">
            HOST PHOTO / LOGO
          </div>
        </div>
      </Container>

      <Container className="pt-12 md:pt-16">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-start">
          <div>
            <Heading>The host</Heading>
            <HostCard />
            <div className="bg-surface border border-border p-5 mt-4">
              <div className="font-display text-text text-[16px] tracking-[0.04em] italic">Recurring guests</div>
              <p className="text-muted text-[13px] leading-[1.6] mt-2">
                Draft-along episodes regularly feature guest hosts from the wider MTG Limited community — credited in
                each episode's notes.
              </p>
            </div>
          </div>
          <div>
            <Heading>Show format</Heading>
            <div className="bg-surface border border-border px-5 py-2">
              {SHOW_FORMAT.map((f) => (
                <div key={f.name} className="flex items-baseline gap-2 py-2.5 border-b border-border last:border-b-0">
                  <span className="font-display text-text text-[15px] tracking-[0.04em] shrink-0">{f.name}</span>
                  <span className="flex-1 border-b border-dotted border-dim relative -top-1" />
                  <span className="text-muted text-[13px] shrink-0">{f.blurb}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Container>

      <Container className="pt-12 md:pt-16">
        <Heading>Other places to find us</Heading>
        <p className="text-muted text-[14px] -mt-1 mb-5">
          Discord is where the conversation lives — but the show has a footprint beyond that.
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-5 items-start">
          <div className="flex flex-col gap-4">
            {COMMUNITY_PLATFORMS.map((platform) => (
              <PlatformCard key={platform.key} platform={platform} />
            ))}
          </div>
          <div className="flex flex-col gap-5">
            <SideCard title="Community guidelines">
              <p className="text-muted text-[13px] leading-[1.6]">
                Be good to each other. No harassment, no spoiler-sniping outside designated channels, no piracy links.
                Hosts and mods enforce.
              </p>
              <a
                href={SITE_LINKS.discord}
                target="_blank"
                rel="noreferrer"
                className="self-start mt-4 inline-flex items-center gap-1.5 font-display tracking-[0.1em] text-[13px] text-green no-underline hover:text-green-2 transition-colors"
              >
                Read the full rules <ArrowRight size={13} />
              </a>
            </SideCard>
            <SideCard title="Submit to Mailbag">
              <p className="text-muted text-[13px] leading-[1.6]">
                Got a question for the show? Drop it in the #mailbag Discord channel or email{" "}
                <a href={SITE_LINKS.mailbag} className="text-green hover:underline underline-offset-2">
                  hello@limitedlevelups.com
                </a>
                .
              </p>
            </SideCard>
          </div>
        </div>
      </Container>
    </PageShell>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return <h2 className="font-display text-text text-[22px] md:text-[26px] tracking-[0.05em] mb-4">{children}</h2>;
}

function SideCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="bg-surface border border-border p-5 flex flex-col">
      <div className="font-display text-text text-[17px] tracking-[0.04em] mb-2.5">{title}</div>
      {children}
    </section>
  );
}
