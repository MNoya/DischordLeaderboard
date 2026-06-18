import type { ReactNode } from "react";
import { SiDiscord, SiYoutube } from "react-icons/si";
import { FaPodcast } from "react-icons/fa6";
import type { IconType } from "react-icons";
import { PageShell } from "../components/PageShell";
import { Container } from "../components/Container";
import { DiscordBand } from "../components/DiscordBand";
import { HostCard } from "../components/HostCard";
import { PlatformCard } from "../components/PlatformCard";
import { ArrowRight } from "../components/Icons";
import {
  COMMUNITY_PLATFORMS,
  COMMUNITY_STATS,
  CONTACT_EMAIL,
  HOSTS,
  SHOW_FORMAT,
  SITE_BLURB,
  SITE_LINKS,
} from "../data/site";

const PILLARS: Array<{ name: string; blurb: string; Icon: IconType; url: string }> = [
  {
    name: "YouTube",
    blurb: "Every episode in video, plus draft-along gameplay and set-review breakdowns.",
    Icon: SiYoutube,
    url: SITE_LINKS.youtube,
  },
  {
    name: "Podcast",
    blurb: "A weekly deep-dive on the live format — listen on Apple, Spotify, or any app.",
    Icon: FaPodcast,
    url: SITE_LINKS.apple,
  },
  {
    name: "Discord",
    blurb: "Where the community lives — drafts, deck checks, trophies, and the leaderboard.",
    Icon: SiDiscord,
    url: SITE_LINKS.discord,
  },
];

export function CommunityPage() {
  return (
    <PageShell subtitle="COMMUNITY">
      <DiscordBand />

      <Container className="pt-12 md:pt-16">
        <Heading>What is Limited Level-Ups?</Heading>
        <p className="text-muted text-[15px] md:text-[16px] leading-[1.7] max-w-[760px]">{SITE_BLURB}</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-7">
          {PILLARS.map((pillar) => (
            <a
              key={pillar.name}
              href={pillar.url}
              target="_blank"
              rel="noreferrer"
              className="group bg-surface border border-border p-5 no-underline transition-colors hover:border-green"
            >
              <span className="inline-flex h-10 w-10 items-center justify-center border border-border2 text-subtle transition-colors group-hover:border-green group-hover:text-green">
                <pillar.Icon className="text-[18px]" size={18} />
              </span>
              <div className="font-display text-text text-[19px] tracking-[0.04em] mt-3.5">{pillar.name}</div>
              <p className="text-muted text-[13px] leading-[1.6] mt-1.5">{pillar.blurb}</p>
            </a>
          ))}
        </div>
      </Container>

      <Container className="pt-12 md:pt-16">
        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-8 lg:gap-12 items-start">
          <div>
            <Heading>Meet the hosts</Heading>
            <div className="flex flex-col gap-4">
              {HOSTS.map((host) => (
                <HostCard key={host.handle} host={host} />
              ))}
            </div>
          </div>
          <div>
            <Heading>How the show works</Heading>
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

      <Container className="pt-12 md:pt-16 pb-4">
        <Heading>Find us everywhere</Heading>
        <p className="text-muted text-[14px] -mt-1 mb-5 max-w-[680px]">
          Discord is the primary hangout — but the show has a footprint across every platform.
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-5 items-start">
          <div className="flex flex-col gap-4">
            {COMMUNITY_PLATFORMS.map((platform) => (
              <PlatformCard key={platform.key} platform={platform} />
            ))}
          </div>
          <div className="flex flex-col gap-5">
            <SideCard title="Support the show">
              <p className="text-muted text-[13px] leading-[1.6]">
                Limited Level-Ups is listener-supported. {COMMUNITY_STATS.patreonSupporters} patrons keep new episodes
                coming every week, with bonus content and a patron-only Discord role from $4/month.
              </p>
              <a
                href={SITE_LINKS.patreon}
                target="_blank"
                rel="noreferrer"
                className="self-start mt-4 inline-flex items-center gap-1.5 font-display tracking-[0.1em] text-[13px] text-green no-underline hover:text-green-2 transition-colors"
              >
                Become a patron <ArrowRight size={13} />
              </a>
            </SideCard>
            <SideCard title="Get in touch">
              <p className="text-muted text-[13px] leading-[1.6]">
                For coaching or business inquiries, email{" "}
                <a href={SITE_LINKS.contact} className="text-green hover:underline underline-offset-2">
                  {CONTACT_EMAIL}
                </a>
                . For everything else, the{" "}
                <a
                  href={SITE_LINKS.discord}
                  target="_blank"
                  rel="noreferrer"
                  className="text-green hover:underline underline-offset-2"
                >
                  Discord
                </a>{" "}
                is the fastest way to reach the community.
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
