import type { ReactNode } from "react";
import { AppHeader } from "../components/AppHeader";
import { Globe } from "../components/Icons";
import { DiscordIcon, PatreonIcon, YoutubeIcon } from "../components/BrandIcons";
import { Footer } from "../components/Footer";
import { CtaPill } from "../components/CtaPill";
import { ScoringExplainer } from "../components/ScoringExplainer";
import { cn } from "../lib/utils";

const DISCORD_URL = "https://discord.com/invite/XWNVT9mxvU";
const PATREON_URL = "https://patreon.com/limitedlevelups";
const GITHUB_URL = "https://github.com/mnoya/DischordLeaderboard";
const SEVENTEEN_LANDS_URL = "https://www.17lands.com";
const PODCAST_URL = "https://limitedlevelups.libsyn.com";
const YOUTUBE_URL = "https://www.youtube.com/@limitedlevel-ups";

export function AboutPage() {
  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="ABOUT" />
      <main className="flex-1 flex flex-col mx-auto w-full max-w-[1040px] px-5 md:px-10 pt-5 md:pt-10 pb-5 md:pb-5 md:relative">
        <Intro />
        <CTA />
        <Rule dense />
        <ScoringExplainer />
        <Rule showOnMobile />
        <Block title="LINKS">
          <LinksBlock />
        </Block>
        <Footer className="mt-auto pt-3 md:mt-0 md:pt-0 md:absolute md:bottom-5 md:right-10" />
      </main>
    </div>
  );
}

function Intro() {
  return (
    <div className="flex flex-col items-center gap-4 mb-8 text-center">
      <p className="text-[18px] md:text-[22px] text-text leading-[1.5]">
        <span className="font-semibold">Limited Level-Ups</span> is a podcast that aims to get you
        better at limited Magic.
      </p>
      <p className="text-[14px] md:text-[15px] text-muted leading-[1.7]">
        This leaderboard ranks Discord members who opt in via{" "}
        <code className="mono text-text bg-surface2 border border-border2 px-1.5 py-px text-[13px]">
          /join
        </code>
        , using their <ExternalLink href={SEVENTEEN_LANDS_URL}>17Lands</ExternalLink> data.
      </p>
    </div>
  );
}

function CTA() {
  return (
    <div className="mb-6 md:mb-8 flex justify-center">
      <a href={DISCORD_URL} target="_blank" rel="noreferrer" className="no-underline">
        <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
          JOIN THE DISCHORD
        </CtaPill>
      </a>
    </div>
  );
}

function Rule({
  dense = false,
  showOnMobile = false,
}: {
  dense?: boolean;
  showOnMobile?: boolean;
}) {
  const visible = dense || showOnMobile;
  const marginClass = dense
    ? "mt-0 mb-5 md:mb-8"
    : showOnMobile
      ? "my-[17px] md:my-8"
      : "my-5 md:my-8";
  return (
    <div className={cn("flex items-center gap-3", marginClass)} aria-hidden="true">
      <span
        className={cn(
          "w-1 h-1 bg-dim rotate-45",
          visible ? "inline-block" : "hidden md:inline-block",
        )}
      />
      <span
        className={cn(
          "flex-1 h-px bg-border",
          visible ? "block" : "hidden md:block",
        )}
      />
      <span
        className={cn(
          "w-1 h-1 bg-dim rotate-45",
          visible ? "inline-block" : "hidden md:inline-block",
        )}
      />
    </div>
  );
}

function Block({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <section>
      <h2 className="font-display text-[16px] md:text-[18px] text-text tracking-[0.18em] mb-3 md:mb-4">
        {title}
      </h2>
      {children}
    </section>
  );
}

function LinksBlock() {
  const links = [
    {
      label: "Patreon",
      url: PATREON_URL,
      value: "patreon.com/limitedlevelups",
      icon: <PatreonIcon size={18} />,
    },
    {
      label: "Discord",
      url: DISCORD_URL,
      value: "discord.com/invite/XWNVT9mxvU",
      icon: <DiscordIcon size={18} />,
    },
    {
      label: "Podcast",
      url: PODCAST_URL,
      value: "limitedlevelups.libsyn.com",
      icon: <Globe size={18} strokeWidth={1.75} />,
    },
    {
      label: "YouTube",
      url: YOUTUBE_URL,
      value: "youtube.com/@limitedlevel-ups",
      icon: <YoutubeIcon size={18} />,
    },
  ];
  return (
    <div className="flex flex-col">
      {links.map((l) => (
        <a
          key={l.label}
          href={l.url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-3 md:gap-4 py-3 border-b border-border last:border-b-0 no-underline group transition-colors hover:bg-surface -mx-2 px-2"
        >
          <span className="text-muted group-hover:text-green transition-colors shrink-0">
            {l.icon}
          </span>
          <span className="font-display text-[14px] md:text-[15px] tracking-[0.06em] text-text shrink-0 w-[90px]">
            {l.label}
          </span>
          <span className="mono text-[12px] md:text-[13px] text-muted group-hover:text-green transition-colors break-all">
            {l.value}
          </span>
        </a>
      ))}
    </div>
  );
}

function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-green hover:underline underline-offset-2"
    >
      {children}
    </a>
  );
}
