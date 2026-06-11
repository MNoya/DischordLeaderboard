import { ArrowRight } from "./Icons";
import { cn } from "../lib/utils";
import type { COMMUNITY_PLATFORMS } from "../data/site";

type Platform = (typeof COMMUNITY_PLATFORMS)[number];

const BADGE: Record<string, string> = {
  youtube: "YT",
  twitch: "TW",
  bluesky: "BS",
  reddit: "RD",
  patreon: "PT",
};

export function PlatformCard({ platform }: { platform: Platform }) {
  return (
    <a
      href={platform.url}
      target="_blank"
      rel="noreferrer"
      className="group flex items-center gap-4 md:gap-5 bg-surface border border-border p-4 md:p-5 no-underline transition-colors hover:border-green"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center border border-border2 mono text-[13px] tracking-[0.06em] text-subtle group-hover:text-green group-hover:border-green transition-colors">
        {BADGE[platform.key] ?? platform.name.slice(0, 2).toUpperCase()}
      </span>
      <div className="flex-1 min-w-0">
        <div className="font-display text-text text-[16px] md:text-[18px] tracking-[0.04em] leading-none">
          {platform.name}
        </div>
        <p className="text-muted text-[13px] leading-[1.5] mt-1.5">{platform.blurb}</p>
        <div className="mono text-[11px] tracking-[0.1em] text-dim mt-2">{platform.stat}</div>
      </div>
      <span
        className={cn(
          "shrink-0 inline-flex items-center gap-1.5 font-display tracking-[0.12em] text-[13px]",
          "text-muted group-hover:text-green transition-colors",
        )}
      >
        {platform.action}
        <ArrowRight size={14} />
      </span>
    </a>
  );
}
