import type { ReactNode, Ref } from "react";
import { SetGlyph } from "../Brand";
import { SectionLabel } from "../SectionLabel";
import { P0P1Countdown } from "./Countdown";
import { P0P1CountdownBar } from "./CountdownBar";
import { P0P1IntroText } from "./P0P1IntroText";
import {
  P0P1_SET_CODE as SET_CODE,
  P0P1_SET_NAME,
  P0P1_VOTING_DEADLINE as VOTING_DEADLINE,
  P0P1_SCORING_DATE as SCORING_DATE,
} from "../../data/p0p1Slots";
import type { P0P1Phase } from "../../data/p0p1Results";

export function P0P1Hero({
  cta,
  innerRef,
  belowIntro,
  phase,
}: {
  cta: ReactNode;
  innerRef?: Ref<HTMLDivElement>;
  belowIntro?: ReactNode;
  phase: P0P1Phase;
}) {
  const isPastDeadline = phase !== "voting";
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
          <P0P1Countdown deadline={VOTING_DEADLINE} scoringDate={SCORING_DATE} size={11} phase={phase} />
        </div>
        {isPastDeadline && (
          <div className="w-full mt-2">
            <P0P1CountdownBar from={VOTING_DEADLINE} to={SCORING_DATE} />
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0 self-stretch flex flex-col items-center justify-center gap-y-3">
        <p className="max-w-[580px] text-center text-subtle text-[14px] leading-[1.55]">
          <P0P1IntroText isPastDeadline={isPastDeadline} multiline />
        </p>
        {belowIntro}
      </div>
      <div className="shrink-0 ml-auto flex justify-end min-w-[280px]">{cta}</div>
    </div>
  );
}
