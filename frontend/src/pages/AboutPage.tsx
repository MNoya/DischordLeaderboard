import type { ReactNode } from "react";
import { AppHeader } from "../components/AppHeader";
import { ArrowRight, Globe } from "../components/Icons";
import { DiscordIcon, PatreonIcon, YoutubeIcon } from "../components/BrandIcons";
import { Footer } from "../components/Footer";
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
        <Block title={<>LEADERBOARD <span className="text-green">POINTS</span></>}>
          <Scoring />
        </Block>
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
        <button
          type="button"
          className="bg-green text-bg cursor-pointer transition-colors hover:bg-green-2 inline-flex items-center gap-3 md:gap-4 py-2.5 md:py-3 pl-5 md:pl-6 pr-6 md:pr-8 border-none"
          style={{ clipPath: "polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)" }}
        >
          <span className="inline-flex items-center justify-center w-9 h-9 md:w-10 md:h-10 rounded-full bg-bg text-text shrink-0">
            <DiscordIcon size={19} />
          </span>
          <span className="font-display text-[17px] md:text-[20px] tracking-[0.14em] leading-none">
            JOIN THE DISCHORD
          </span>
          <ArrowRight size={18} />
        </button>
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

function Scoring() {
  return (
    <div className="flex flex-col gap-5 md:gap-6">
      <div className="bg-surface border border-border2 px-2.5 py-4 md:px-6 md:py-5 mono tracking-tight">
        <div
          className="flex flex-nowrap items-center justify-center md:justify-start whitespace-nowrap"
          style={{ fontSize: "clamp(9px, 2.8vw, 17px)" }}
        >
          <span className="relative inline-block mr-[0.4em] align-middle">
            <span className="relative -top-[0.1em] text-text text-[2em] leading-none">Σ</span>
            <span className="absolute left-1/2 -translate-x-1/2 top-full -mt-[0.1em] text-green text-[0.6em] tracking-normal leading-none">
              queues
            </span>
          </span>
          <span className="text-text">Trophies</span>
          <span className="text-green mx-[0.35em]">×</span>
          <span className="text-text">Weight</span>
          <span className="text-green mx-[0.35em]">×</span>
          <span className="text-text">Trophy Rate</span>
          <span className="text-green mx-[0.35em]">×</span>
          <span className="text-text">Confidence</span>
          <span className="text-green mx-[0.35em] text-[1.3em] align-middle">+</span>
          <span className="text-text">Pod</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
        <div className="flex flex-col gap-2 text-[13px] md:text-[14px] text-muted leading-[1.6]">
          <p>
            Each queue is scored based on <span className="text-text">trophies</span>, then summed
            into a single total.<br/>
            The goal is to reward performance while considering volume.</p>
          <p>
            <span className="text-text">Weight</span> values events by difficulty, cost, and
            prestige.
          </p>
          <p>
            <span className="text-text">Confidence</span> factor{" "}
            <code className="mono text-muted text-[11px] md:text-[12px] whitespace-nowrap">
              trophies / (trophies + 2)
            </code>{" "}
            provides sample-size protection.
          </p>
          <p>
            Filtering by format or deck colors recalculates points using only the matching events.
          </p>
        </div>

        <div className="flex flex-col">
          <div className="mono text-[10px] text-muted tracking-[0.24em] pb-2 flex justify-between">
            <span>QUEUE</span>
            <span>WEIGHT</span>
          </div>
          <Leader label="Premier Draft" value="10" />
          <Leader label="Traditional Draft" value="8" />
          <Leader label="Sealed" note="Includes Arena Direct" value="8" />
          <Leader label="Quick & Pick Two Draft" value="4" />
          <Leader label="ALCQ Draft 1" value="30" />
          <Leader label="ALCQ Draft 2" note="Per Game Win" value="10" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-12">
        <div className="flex flex-col gap-2 text-[13px] md:text-[14px] text-muted leading-[1.6]">
          <p>
            <span className="text-text">Pod Drafts</span> score on their own, adding flat points
            directly to the total with no other factors applied.
          </p>
        </div>

        <div className="flex flex-col">
          <div className="mono text-[10px] text-muted tracking-[0.24em] pb-2 flex justify-between">
            <span>POD DRAFT</span>
            <span>POINTS</span>
          </div>
          <Leader label="Trophy" value="5" />
          <Leader label="2-1 Record" value="2" />
        </div>
      </div>
    </div>
  );
}

function Leader({
  label,
  note,
  value,
}: {
  label: string;
  note?: string;
  value: ReactNode;
}) {
  return (
    <div className="flex items-baseline gap-2 py-1.5">
      <span className="font-display text-[13px] md:text-[15px] tracking-[0.04em] text-text shrink-0">
        {label}
      </span>
      {note && (
        <span className="text-[11px] md:text-[12px] text-muted italic shrink-0">{note}</span>
      )}
      <span className="flex-1 border-b border-dotted border-dim relative -top-1.5" />
      <span className="mono text-[13px] md:text-[14px] text-muted tabular-nums">{value}</span>
    </div>
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
