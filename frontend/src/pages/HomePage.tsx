import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { PageShell } from "../components/PageShell";
import { Container } from "../components/Container";
import { SectionLabel } from "../components/SectionLabel";
import { EpisodeCard } from "../components/EpisodeCard";
import { DiscordBand } from "../components/DiscordBand";
import { HostCard } from "../components/HostCard";
import { CtaPill } from "../components/CtaPill";
import { ArrowRight } from "../components/Icons";
import { PatreonIcon } from "../components/BrandIcons";
import { useEpisodes } from "../data/hooks";
import { EPISODE_CATEGORIES, type Episode } from "../data/episodes";
import { LISTEN_ON, SITE_LINKS, SITE_PITCH, SITE_STATS, SITE_TAGLINE } from "../data/site";
import { cn } from "../lib/utils";

export function HomePage() {
  const { data: episodes } = useEpisodes();
  const latest = episodes?.[0];
  const recent = episodes?.slice(0, 4) ?? [];
  return (
    <PageShell subtitle="PODCAST">
      <Hero latest={latest} />
      <BrowseByCategory episodes={episodes} />
      <RecentEpisodes episodes={recent} loading={!episodes} />
      <DiscordBand />
      <AboutSupport />
    </PageShell>
  );
}

function Hero({ latest }: { latest?: Episode }) {
  return (
    <section
      className="border-b border-border"
      style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
    >
      <Container className="py-16 md:py-24 flex flex-col items-center text-center">
        <SectionLabel size={12} letterSpacing="0.26em" color="#2ee85c">
          LIMITED LEVEL-UPS · A MAGIC: THE GATHERING PODCAST
        </SectionLabel>
        <h1 className="font-display text-text leading-[0.95] tracking-[0.01em] mt-5 text-[44px] md:text-[72px] max-w-[15ch]">
          {SITE_TAGLINE}
        </h1>
        <p className="text-subtle text-[15px] md:text-[17px] leading-[1.6] mt-5 max-w-[58ch]">{SITE_PITCH}</p>

        <div className="flex flex-wrap items-center justify-center gap-3 mt-8">
          <a
            href={latest?.link ?? SITE_LINKS.podcast}
            target="_blank"
            rel="noreferrer"
            className="no-underline"
          >
            <CtaPill size="md" icon={<span className="text-[13px] pl-0.5">▶</span>}>
              LATEST EPISODE
            </CtaPill>
          </a>
          {LISTEN_ON.filter((l) => l.label !== "RSS").map((l) => (
            <a
              key={l.label}
              href={l.url}
              target="_blank"
              rel="noreferrer"
              className="font-display tracking-[0.12em] text-[15px] text-text border border-border2 px-5 py-2.5 no-underline transition-colors hover:border-green hover:text-green"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="w-full max-w-[760px] border-t border-border mt-12 pt-8 grid grid-cols-2 md:grid-cols-4 gap-y-6">
          {SITE_STATS.map((s) => (
            <div key={s.label} className="flex flex-col items-center gap-1.5">
              <span className="font-display text-green text-[34px] md:text-[40px] leading-none tabular-nums">
                {s.value}
              </span>
              <span className="mono text-[11px] tracking-[0.14em] text-muted uppercase">{s.label}</span>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}

function BrowseByCategory({ episodes }: { episodes?: Episode[] }) {
  const counts = new Map<string, number>();
  for (const ep of episodes ?? []) {
    counts.set(ep.category, (counts.get(ep.category) ?? 0) + 1);
  }
  return (
    <Container className="pt-12 md:pt-16">
      <SectionLabel letterSpacing="0.24em">BROWSE BY CATEGORY</SectionLabel>
      <div className="flex flex-wrap gap-2.5 mt-4">
        {EPISODE_CATEGORIES.map((category) => (
          <Link
            key={category}
            to={`/episodes?category=${encodeURIComponent(category)}`}
            className="group inline-flex items-center gap-2 border border-border bg-surface px-4 py-2 no-underline transition-colors hover:border-green"
          >
            <span className="font-display tracking-[0.06em] text-[14px] text-text group-hover:text-green transition-colors">
              {category}
            </span>
            {counts.has(category) ? (
              <span className="mono text-[11px] text-muted tabular-nums">{counts.get(category)}</span>
            ) : null}
          </Link>
        ))}
      </div>
    </Container>
  );
}

function RecentEpisodes({ episodes, loading }: { episodes: Episode[]; loading: boolean }) {
  return (
    <Container className="pt-12 md:pt-14">
      <div className="flex items-end justify-between gap-4 mb-6">
        <h2 className="font-display text-text text-[24px] md:text-[28px] tracking-[0.04em]">Recent Episodes</h2>
        <Link
          to="/episodes"
          className="font-display tracking-[0.1em] text-[14px] text-green no-underline inline-flex items-center gap-1.5 hover:text-green-2 transition-colors"
        >
          View full archive <ArrowRight size={14} />
        </Link>
      </div>
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-x-5 gap-y-8">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="aspect-video bg-surface border border-border animate-pulse" />
          ))}
        </div>
      ) : episodes.length ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-x-5 gap-y-8">
          {episodes.map((ep) => (
            <EpisodeCard key={ep.id} episode={ep} />
          ))}
        </div>
      ) : (
        <p className="text-muted text-[14px]">Episodes are taking a minute to load — check back shortly.</p>
      )}
    </Container>
  );
}

function AboutSupport() {
  return (
    <Container className="pt-12 md:pt-16 grid grid-cols-1 md:grid-cols-2 gap-5">
      <SummaryCard title="About the show">
        <p className="text-muted text-[14px] leading-[1.7]">
          A weekly Magic: the Gathering Limited podcast hosted by Alex (Chord_O_Calls) — breaking down every new set
          since November 2020.
        </p>
        <div className="mt-4">
          <HostCard />
        </div>
        <Link
          to="/community"
          className={cn(
            "self-start mt-4 font-display tracking-[0.1em] text-[14px] text-green no-underline",
            "inline-flex items-center gap-1.5 hover:text-green-2 transition-colors",
          )}
        >
          Read more <ArrowRight size={14} />
        </Link>
      </SummaryCard>

      <SummaryCard title="Support the show">
        <p className="text-muted text-[14px] leading-[1.7]">
          LLU is listener-supported. Patreon backers get bonus content, early access to set previews, ad-free feeds,
          and a private Discord channel.
        </p>
        <a href={SITE_LINKS.patreon} target="_blank" rel="noreferrer" className="self-start mt-5 no-underline">
          <CtaPill size="md" icon={<PatreonIcon size={16} />}>
            BECOME A PATRON
          </CtaPill>
        </a>
      </SummaryCard>
    </Container>
  );
}

function SummaryCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="bg-surface border border-border p-5 md:p-6 flex flex-col">
      <h2 className="font-display text-text text-[20px] tracking-[0.06em] mb-3">{title}</h2>
      {children}
    </section>
  );
}
