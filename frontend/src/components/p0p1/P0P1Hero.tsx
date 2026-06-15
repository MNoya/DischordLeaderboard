import type { ReactNode, Ref } from "react";
import { SetGlyph } from "../Brand";
import { SectionLabel } from "../SectionLabel";
import { P0P1Countdown } from "./Countdown";
import { P0P1_SET_CODE as SET_CODE, P0P1_SET_NAME, P0P1_VOTING_DEADLINE as VOTING_DEADLINE } from "../../data/p0p1Slots";

const SEVENTEEN_LANDS_URL = "https://www.17lands.com/card_data";

export function P0P1Hero({
  cta,
  innerRef,
  belowIntro,
}: {
  cta: ReactNode;
  innerRef?: Ref<HTMLDivElement>;
  belowIntro?: ReactNode;
}) {
  return (
    <div ref={innerRef} className="sticky top-0 z-30 px-10 py-5 border-b border-border bg-surface flex flex-wrap items-center gap-x-8 gap-y-3">
      <SetGlyph code={SET_CODE} size={84} />
      <div className="shrink-0">
        <SectionLabel size={13}>PACK 0, PICK 1</SectionLabel>
        <div className="flex items-baseline gap-3.5 mt-0.5">
          <span className="font-display tracking-[0.04em]" style={{ fontSize: 56, lineHeight: 0.9 }}>
            {SET_CODE}
          </span>
          <span className="font-display text-[22px] text-muted tracking-[0.06em]">{P0P1_SET_NAME.toUpperCase()}</span>
        </div>
        <div className="mono text-[11px] mt-1">
          <P0P1Countdown deadline={VOTING_DEADLINE} size={11} />
        </div>
      </div>
      <div className="flex-1 min-w-0 self-stretch flex flex-col items-center justify-center gap-y-3">
        <p className="max-w-[580px] text-center text-subtle text-[14px] leading-[1.55]">
          Put together a team of eight cards from {P0P1_SET_NAME}.
          <br />
          Six weeks after release, teams are ranked by their total{" "}
          <a
            href={SEVENTEEN_LANDS_URL}
            target="_blank"
            rel="noreferrer"
            className="text-green hover:underline underline-offset-2"
          >
            17Lands GIH win rate
          </a>
          .
        </p>
        {belowIntro}
      </div>
      {cta && <div className="shrink-0 ml-auto">{cta}</div>}
    </div>
  );
}
