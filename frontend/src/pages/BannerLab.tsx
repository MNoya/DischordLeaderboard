import { useState } from "react";
import { ALogo } from "../components/Brand";
import { cn } from "../lib/utils";

// Scratch page for comparing header / banner wordmark treatments side by side
// at desktop and mobile widths. Not linked from nav — reach it at /banner.

const SECTIONS = ["HOME", "EPISODES", "LEADERBOARD", "TIER LIST"];

const NAV = ["P0 P1", "EPISODES", "TIER LIST", "LEADERBOARD"];

function DesktopNav({ section }: { section: string }) {
  return (
    <nav className="flex gap-2 font-display text-[19px] tracking-[0.14em]">
      {NAV.map((label) => (
        <span
          key={label}
          className={cn(
            "py-2.5 px-5 border whitespace-nowrap",
            label === section ? "bg-green text-bg border-green" : "text-text border-transparent",
          )}
        >
          {label}
        </span>
      ))}
    </nav>
  );
}

function MenuButton() {
  return (
    <span className="w-11 h-11 border border-border2 text-muted flex items-center justify-center shrink-0">
      <span className="text-[28px] leading-none">≡</span>
    </span>
  );
}

// A — Lockup + rule: brand and section are siblings split by a vertical hairline.
function VariantA({ section, mobile }: { section: string; mobile?: boolean }) {
  if (mobile) {
    return (
      <div className="flex items-center gap-3 pl-1">
        <ALogo size={40} />
        <div className="flex items-center gap-2.5">
          <span className="font-display text-text text-[18px] tracking-[0.07em] leading-none">LIMITED LEVEL-UPS</span>
          <span className="w-px h-4 bg-border2" />
          <span className="font-display text-green text-[15px] tracking-[0.14em] leading-none">{section}</span>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-6">
      <ALogo size={55} />
      <div className="flex items-center gap-5">
        <span className="font-display text-text text-[27px] tracking-[0.09em] leading-none">LIMITED LEVEL-UPS</span>
        <span className="w-px h-7 bg-border2" />
        <span className="font-display text-green text-[27px] tracking-[0.18em] leading-none">{section}</span>
      </div>
    </div>
  );
}

// B — Section-first: the logo carries the name, a quiet mono eyebrow keeps the
// brand present, and the section becomes the hero.
function VariantB({ section, mobile }: { section: string; mobile?: boolean }) {
  if (mobile) {
    return (
      <div className="flex items-center gap-3 pl-1">
        <ALogo size={40} />
        <div className="flex flex-col justify-center">
          <span className="font-mono text-muted text-[8px] tracking-[0.28em] leading-none mb-1">LIMITEDLEVELUPS</span>
          <span className="font-display text-green text-[20px] tracking-[0.1em] leading-none">{section}</span>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-6">
      <ALogo size={55} />
      <div className="flex flex-col justify-center">
        <span className="font-mono text-muted text-[10px] tracking-[0.3em] leading-none mb-1.5">LIMITEDLEVELUPS.COM</span>
        <span className="font-display text-green text-[31px] tracking-[0.08em] leading-none">{section}</span>
      </div>
    </div>
  );
}

// C — Refined stack: the current two-line idea with tighter proportions and
// open tracking on the green section label.
function VariantC({ section, mobile }: { section: string; mobile?: boolean }) {
  if (mobile) {
    return (
      <div className="flex items-center gap-3 pl-1">
        <ALogo size={40} />
        <div className="flex flex-col">
          <span className="font-display text-text text-[18px] leading-[0.95] tracking-[0.08em]">LIMITED LEVEL-UPS</span>
          <span className="font-display text-green text-[11px] tracking-[0.22em] leading-none mt-[3px]">{section}</span>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-6">
      <ALogo size={55} />
      <div className="flex flex-col">
        <span className="font-display text-text text-[26px] leading-[0.95] tracking-[0.09em]">LIMITED LEVEL-UPS</span>
        <span className="font-display text-green text-[14px] tracking-[0.28em] leading-none mt-1">{section}</span>
      </div>
    </div>
  );
}

// D — Section tag: section rendered as an outlined green chip, echoing the
// app's existing CategoryTag vernacular.
function VariantD({ section, mobile }: { section: string; mobile?: boolean }) {
  if (mobile) {
    return (
      <div className="flex items-center gap-2.5 pl-1">
        <ALogo size={40} />
        <span className="font-display text-text text-[18px] tracking-[0.07em] leading-none">LIMITED LEVEL-UPS</span>
        <span className="font-display text-green border border-green/50 px-2 py-0.5 text-[12px] tracking-[0.14em] leading-none">
          {section}
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-5">
      <ALogo size={55} />
      <span className="font-display text-text text-[27px] tracking-[0.09em] leading-none">LIMITED LEVEL-UPS</span>
      <span className="font-display text-green border border-green/50 px-2.5 py-1 text-[15px] tracking-[0.18em] leading-none">
        {section}
      </span>
    </div>
  );
}

const VARIANTS = [
  { key: "A", title: "Lockup + rule", note: "Brand and section as siblings split by a vertical hairline. The rule encodes the brand→location relationship instead of decorating it.", render: VariantA },
  { key: "B", title: "Section-first", note: "The logo carries the name; a quiet mono eyebrow keeps it present; the section becomes the hero. Kills the repeated-wordmark redundancy.", render: VariantB },
  { key: "C", title: "Refined stack", note: "Today's two-line stack, retuned: tighter proportions and open tracking on the green section label.", render: VariantC },
  { key: "D", title: "Section tag", note: "Section rendered as an outlined green chip, echoing the app's existing CategoryTag vernacular.", render: VariantD },
];

function DesktopHeader({ children, section }: { children: React.ReactNode; section: string }) {
  return (
    <header className="border-b border-border flex items-center justify-between bg-bg py-4 pl-10 pr-6">
      {children}
      <DesktopNav section={section} />
    </header>
  );
}

function MobileHeader({ children }: { children: React.ReactNode }) {
  return (
    <header className="border-b border-border flex items-center justify-between bg-bg py-1.5 px-3">
      {children}
      <MenuButton />
    </header>
  );
}

export function BannerLab() {
  const [section, setSection] = useState("EPISODES");

  return (
    <div className="min-h-screen bg-bg text-text font-body">
      <div className="max-w-[1200px] mx-auto px-6 py-10">
        <div className="flex items-baseline justify-between flex-wrap gap-4 mb-2">
          <h1 className="font-display text-[40px] tracking-[0.06em] leading-none">HEADER / BANNER LAB</h1>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-muted tracking-[0.2em] mr-1">SECTION</span>
            {SECTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSection(s)}
                className={cn(
                  "font-display text-[14px] tracking-[0.14em] px-3 py-1.5 border transition-colors",
                  s === section ? "bg-green text-bg border-green" : "text-subtle border-border hover:border-border2",
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <p className="text-muted text-sm mb-12 max-w-[680px]">
          Four header treatments at desktop and mobile width. The logo badge already says LIMITED LEVEL-UPS, so each
          direction handles the repeated wordmark differently. Switch the active section above to see how each holds up.
        </p>

        <div className="flex flex-col gap-16">
          {VARIANTS.map((v) => (
            <section key={v.key}>
              <div className="flex items-baseline gap-3 mb-1">
                <span className="font-display text-green text-[22px] tracking-[0.1em] leading-none">{v.key}</span>
                <h2 className="font-display text-text text-[22px] tracking-[0.08em] leading-none">{v.title}</h2>
              </div>
              <p className="text-muted text-sm mb-5 max-w-[680px]">{v.note}</p>

              <div className="grid grid-cols-1 lg:grid-cols-[1fr_390px] gap-6 items-start">
                <div>
                  <span className="font-mono text-[10px] text-dim tracking-[0.25em] block mb-2">DESKTOP</span>
                  <div className="border border-border2 overflow-hidden">
                    <DesktopHeader section={section}>
                      <v.render section={section} />
                    </DesktopHeader>
                  </div>
                </div>
                <div>
                  <span className="font-mono text-[10px] text-dim tracking-[0.25em] block mb-2">MOBILE · 390</span>
                  <div className="border border-border2 overflow-hidden w-[390px] max-w-full">
                    <MobileHeader>
                      <v.render section={section} mobile />
                    </MobileHeader>
                  </div>
                </div>
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
