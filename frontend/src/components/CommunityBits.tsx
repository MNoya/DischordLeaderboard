import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  GraduationCap,
  Layers,
  Leaf,
  ListOrdered,
  type LucideIcon,
  Mic,
  Package,
} from "lucide-react";
import { SiPatreon, SiTwitch, SiX, SiYoutube } from "react-icons/si";
import type { IconType } from "react-icons";
import { AAvatar } from "./Brand";
import { ChamferCta } from "./ChamferCta";
import { CATEGORY_COLOR } from "./CategoryTag";
import { SectionLabel } from "./SectionLabel";
import { ArrowRight, Globe } from "./Icons";
import { cn } from "../lib/utils";
import { categoryHref, COMMUNITY_SUPPORT_NOTE, type CommunityLink } from "../data/community";
import { EPISODE_CATEGORIES, type EpisodeCategory } from "../data/episodes";
import { SITE_LINKS, type Host } from "../data/site";

export function CommunityHeading({ children }: { children: ReactNode }) {
  return (
    <SectionLabel size={16} letterSpacing="0.18em" className="text-subtle">
      {children}
    </SectionLabel>
  );
}

export function SectionPanel({
  title,
  icon,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn("flex flex-col rounded-xl border border-border bg-surface p-5", className)}>
      <div className="flex h-12 items-center gap-4">
        {icon ? <span className="flex h-12 w-12 shrink-0 items-center justify-center text-subtle">{icon}</span> : null}
        <span className="font-display text-text text-[19px] tracking-[0.03em]">{title}</span>
      </div>
      <div className={cn("flex-1 pt-4", bodyClassName)}>{children}</div>
    </section>
  );
}

const CATEGORY_ICON: Record<EpisodeCategory, LucideIcon> = {
  "Set Review": BookOpen,
  Metagame: BarChart3,
  Draft: Layers,
  Sealed: Package,
  Rankings: ListOrdered,
  Coaching: GraduationCap,
  Guest: Mic,
  Evergreen: Leaf,
};

export function HostMug({ host, size = 88 }: { host: Host; size?: number }) {
  return <AAvatar displayName={host.name} avatarUrl={host.photo} size={size} green />;
}

const HOST_LINK_ICON: Record<string, IconType> = {
  Twitch: SiTwitch,
  YouTube: SiYoutube,
};

export function HostBlock({ host }: { host: Host }) {
  const twitter = host.links.find((link) => link.label === "Twitter");
  const otherLinks = host.links.filter((link) => link.label !== "Twitter");
  return (
    <div className="flex gap-4">
      <HostMug host={host} />
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <div className="font-display text-text text-[17px] tracking-[0.04em] truncate">
            {host.name}{" "}
            {twitter ? (
              <a
                href={twitter.url}
                target="_blank"
                rel="noreferrer"
                aria-label={`${host.handle} on X`}
                className="inline-flex items-center gap-1 text-muted no-underline transition-colors hover:text-green"
              >
                @{host.handle}
                <SiX size={13} />
              </a>
            ) : (
              <span className="text-muted">{host.handle}</span>
            )}
          </div>
          <div className="flex items-center gap-2.5 shrink-0">
            {otherLinks.map((link) => {
              const Icon = HOST_LINK_ICON[link.label];
              return (
                <a
                  key={link.label}
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={link.label}
                  className="text-subtle transition-colors hover:text-green"
                >
                  {Icon ? <Icon size={16} /> : link.label}
                </a>
              );
            })}
          </div>
        </div>
        <div className="mono text-[11px] tracking-[0.12em] text-green uppercase mt-1">{host.role}</div>
        <p className="text-muted text-[13px] leading-[1.6] mt-2">{host.bio}</p>
      </div>
    </div>
  );
}

export function EventCard({ event, className }: { event: CommunityLink; className?: string }) {
  return (
    <Link
      to={event.to}
      className={cn(
        "group relative flex gap-5 overflow-hidden rounded-xl bg-surface border border-border p-6 no-underline transition-colors hover:border-green",
        className,
      )}
    >
      <event.Icon
        size={132}
        className="pointer-events-none absolute -right-5 -bottom-6 text-border2/50 transition-colors duration-200 group-hover:text-green/15"
      />
      <span className="relative flex h-16 w-16 shrink-0 items-center justify-center text-subtle transition-colors group-hover:text-green">
        <event.Icon size={44} />
      </span>
      <div className="relative flex min-w-0 flex-1 flex-col">
        <div className="font-display text-text text-[19px] tracking-[0.03em] group-hover:text-green transition-colors">
          {event.title}
        </div>
        <p className="text-muted text-[13.5px] leading-[1.65] mt-2 flex-1">{event.blurb}</p>
        <span className="inline-flex items-center gap-1.5 font-display tracking-[0.1em] text-[12px] text-muted group-hover:text-green transition-colors mt-4">
          {event.cta}
          <ArrowRight size={13} />
        </span>
      </div>
    </Link>
  );
}

export function CommunityLinks() {
  const links = [
    { label: "Patreon", url: SITE_LINKS.patreon, icon: <SiPatreon size={18} /> },
    { label: "Podcast", url: SITE_LINKS.podcast, icon: <Globe size={18} strokeWidth={1.75} /> },
  ];
  return (
    <div className="flex flex-col max-w-[480px]">
      {links.map((link) => (
        <a
          key={link.label}
          href={link.url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-3 md:gap-4 py-3 border-b border-border last:border-b-0 no-underline group transition-colors hover:bg-surface -mx-2 px-2"
        >
          <span className="text-subtle group-hover:text-green transition-colors shrink-0">{link.icon}</span>
          <span className="font-display text-[14px] md:text-[15px] tracking-[0.06em] text-text shrink-0 w-[90px]">
            {link.label}
          </span>
          <span className="mono text-[12px] md:text-[13px] text-muted group-hover:text-green transition-colors break-all">
            {displayUrl(link.url)}
          </span>
        </a>
      ))}
    </div>
  );
}

function displayUrl(url: string) {
  return url.replace(/^https?:\/\//, "");
}

export function SupportCard() {
  return (
    <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <p className="text-muted text-[13.5px] leading-[1.6]">{COMMUNITY_SUPPORT_NOTE}</p>
      <ChamferCta
        label="BECOME A PATRON"
        href={SITE_LINKS.patreon}
        target="_blank"
        className="shrink-0 whitespace-nowrap"
      />
    </div>
  );
}

export function ShowTopics({ topics }: { topics?: readonly { category: EpisodeCategory; label: string }[] }) {
  const items = topics ?? EPISODE_CATEGORIES.map((category) => ({ category, label: category }));
  return (
    <div className="flex flex-wrap gap-2">
      {items.map(({ category, label }) => {
        const Icon = CATEGORY_ICON[category];
        return (
          <Link
            key={category}
            to={categoryHref(category)}
            className="group inline-flex items-center gap-2 rounded-lg bg-surface2 px-3 py-2 no-underline transition-colors hover:bg-bg/40"
          >
            <Icon size={16} strokeWidth={2} className={cn("shrink-0", CATEGORY_COLOR[category])} />
            <span className="font-display uppercase tracking-[0.06em] text-[13px] text-text transition-colors group-hover:text-green">
              {label}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
