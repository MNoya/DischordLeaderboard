import { AAvatar } from "./Brand";
import { ExternalLink } from "./Icons";
import { HOST } from "../data/site";

export function HostCard() {
  return (
    <div className="bg-surface border border-border p-5 flex gap-4">
      <AAvatar displayName={HOST.name} size={56} green />
      <div className="min-w-0">
        <div className="font-display text-text text-[17px] tracking-[0.04em]">
          {HOST.name} <span className="text-muted">— {HOST.handle}</span>
        </div>
        <p className="text-muted text-[13px] leading-[1.6] mt-2">{HOST.bio}</p>
        <div className="flex flex-wrap gap-2 mt-3">
          {HOST.socials.map((s) => (
            <a
              key={s.label}
              href={s.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 border border-border2 px-2.5 py-1 mono text-[11px] tracking-[0.08em] text-subtle no-underline transition-colors hover:border-green hover:text-green"
            >
              {s.label}
              <ExternalLink size={11} />
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
