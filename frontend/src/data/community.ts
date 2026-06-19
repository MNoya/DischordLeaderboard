import { GiProgression, GiRoundTable } from "react-icons/gi";
import { type LucideIcon, MessagesSquare, Rocket, TrendingUp, Trophy } from "lucide-react";
import type { IconType } from "react-icons";
import { categorySlug, type EpisodeCategory } from "./episodes";
import { useDiscordStats } from "./hooks";
import { DISCORD_BLURB, SITE_BLURB_PARAGRAPHS } from "./site";

export const COMMUNITY_DISCORD_PITCH = DISCORD_BLURB.replace("The Limited Level-Ups Discord is a ", "A ");

export const COMMUNITY_DISCORD_HEADING = "A home for Limited players";

export const COMMUNITY_INTRO_PARAGRAPHS = [
  SITE_BLURB_PARAGRAPHS[0],
  "Whether you're looking to get your first trophy, sharpen your fundamentals, or compete at the highest level, " +
    "you'll find a community of Limited enthusiasts ready to help you level up your game.",
];

export interface CommunityHighlight {
  Icon: LucideIcon;
  text: string;
}

export const COMMUNITY_HIGHLIGHTS: CommunityHighlight[] = [
  { Icon: MessagesSquare, text: "Discuss the latest Limited formats and upcoming sets" },
  { Icon: TrendingUp, text: "Get help with deckbuilding, picks, and gameplay" },
  { Icon: Rocket, text: "Play in community organized events" },
  { Icon: Trophy, text: "Connect with dedicated Limited players" },
];

export const COMMUNITY_SHOW_NOTE =
  "TBD: New episodes most weeks since 2020 — set reviews on release week, plus draft-alongs, sealed prep, rankings, and " +
  "strategy, on YouTube and every podcast app.";

export const COMMUNITY_SUPPORT_NOTE =
  "TBD: Your patronage keeps the show running by helping to pay for the costs of the show, and allows us to " +
  "produce more content in both audio and video form.We have a bunch of rewards to help you become a better " +
  "player when you choose to support the show!";

export const COMMUNITY_SHOW_TOPICS: Array<{ category: EpisodeCategory; label: string }> = [
  { category: "Set Review", label: "Set reviews" },
  { category: "Metagame", label: "Format updates" },
  { category: "Coaching", label: "Coaching" },
  { category: "Evergreen", label: "Evergreen episodes" },
];

export interface CommunityLink {
  title: string;
  blurb: string;
  to: string;
  cta: string;
  Icon: IconType;
}

export const COMMUNITY_EVENTS: CommunityLink[] = [
  {
    title: "Community leaderboard",
    blurb:
      "TBD: Link your 17lands profile and your trophies and results show up under your name — a shared record of " +
      "everyone's drafts for the set.",
    to: "/leaderboard",
    cta: "See the board",
    Icon: GiProgression,
  },
  {
    title: "Weekly pod drafts",
    blurb:
      "TBD: Eight players draft a pod together in Draftmancer, then play their matches out on MTGA. Every pick is saved " +
      "as a replay you can revisit afterward.",
    to: "/pods",
    cta: "See the pods",
    Icon: GiRoundTable,
  },
];

export function useCommunityStats(): { members?: number; online?: number } {
  const { data } = useDiscordStats();
  return { members: data?.memberCount, online: data?.onlineCount };
}

export function categoryHref(category: EpisodeCategory): string {
  return `/episodes/${categorySlug(category)}`;
}
