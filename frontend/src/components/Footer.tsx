import { GithubIcon } from "./BrandIcons";
import { cn } from "../lib/utils";

const GITHUB_URL = "https://github.com/mnoya/DischordLeaderboard";

export function Footer({ className, updated }: { className?: string; updated?: string }) {
  return (
    <footer
      className={cn(
        "flex items-center justify-between gap-3 text-[11px] md:text-[12px] text-muted",
        className,
      )}
    >
      <span className="mono">
        {updated ? <>UPDATED {updated}</> : null}
      </span>
      <a
        href={GITHUB_URL}
        target="_blank"
        rel="noreferrer"
        aria-label="View source on GitHub"
        className="group inline-flex items-center gap-2 no-underline text-muted hover:text-green transition-colors"
      >
        <span>
          Made by <span className="text-text group-hover:text-green transition-colors">Noya</span>
        </span>
        <GithubIcon size={14} />
      </a>
    </footer>
  );
}
