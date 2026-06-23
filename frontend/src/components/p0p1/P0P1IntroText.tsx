import { Fragment, type ReactNode } from "react";
import {
  P0P1_SET_NAME,
  P0P1_VOTING_DEADLINE,
  P0P1_SCORING_DATE,
  SLOTS,
} from "../../data/p0p1Slots";

const SEVENTEEN_LANDS_URL = "https://www.17lands.com/card_data";

const setName = <span className="font-semibold text-text">{P0P1_SET_NAME}</span>;

const winRateLink = (
  <a
    href={SEVENTEEN_LANDS_URL}
    target="_blank"
    rel="noreferrer"
    className="text-green hover:underline underline-offset-2"
  >
    17Lands GIH win rate
  </a>
);

export function P0P1IntroText({
  isPastDeadline,
  multiline = false,
}: {
  isPastDeadline?: boolean;
  multiline?: boolean;
}) {
  const cardCount = spellOut(SLOTS.length);
  const windowText = describeDuration(P0P1_SCORING_DATE.getTime() - P0P1_VOTING_DEADLINE.getTime());

  const sentences: ReactNode[] = isPastDeadline
    ? [
        <>Participants have put in their predictions for {setName}.</>,
        <>Check out the most popular picks below, then come back once they're ranked by {winRateLink}, {windowText} after release.</>,
      ]
    : [
        <>Put together a team of {cardCount} cards from {setName}.</>,
        <>{capitalize(windowText)} after release, teams are ranked by their total {winRateLink}.</>,
      ];

  return (
    <>
      {sentences.map((sentence, i) => (
        <Fragment key={i}>
          {i > 0 && (multiline ? <br /> : " ")}
          {sentence}
        </Fragment>
      ))}
    </>
  );
}

const NUMBER_WORDS = [
  "zero", "one", "two", "three", "four", "five", "six", "seven",
  "eight", "nine", "ten", "eleven", "twelve",
];

function spellOut(n: number): string {
  return NUMBER_WORDS[n] ?? String(n);
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function describeDuration(ms: number): string {
  const days = Math.round(ms / (24 * 60 * 60 * 1000));
  if (days % 7 === 0) {
    const weeks = days / 7;
    return `${spellOut(weeks)} ${weeks === 1 ? "week" : "weeks"}`;
  }
  return `${spellOut(days)} ${days === 1 ? "day" : "days"}`;
}
