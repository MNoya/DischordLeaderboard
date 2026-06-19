// Single source of truth for the community site's static content — external
// links, the mission blurbs, and hosts. Pages and the footer read from here so
// a copy or URL change cascades everywhere instead of being duplicated per page.

export const SITE_LINKS = {
  discord: "https://discord.com/invite/XWNVT9mxvU",
  patreon: "https://patreon.com/limitedlevelups",
  github: "https://github.com/mnoya/DischordLeaderboard",
  seventeenLands: "https://www.17lands.com",
  podcast: "https://limitedlevelups.libsyn.com",
  youtube: "https://www.youtube.com/@limitedlevel-ups",
  twitch: "https://www.twitch.tv/chord_o_calls",
  apple: "https://podcasts.apple.com/us/podcast/limited-level-ups/id1486488039",
  spotify: "https://open.spotify.com/show/7LUZexiWvU1LM5xBpA7h2X",
  rss: "https://feeds.libsyn.com/limitedlevelups/rss",
  contact: "mailto:chordocoach@gmail.com",
} as const;

export const CONTACT_EMAIL = "chordocoach@gmail.com";

export const DISCORD_GUILD_ID = "775371722065051658";
export const DISCORD_INVITE_CODE = "XWNVT9mxvU";

export function discordEventLink(eventId: string): string {
  return `https://discord.com/events/${DISCORD_GUILD_ID}/${eventId}`;
}

// Alex-approved copy — the canonical blurbs. SITE_BLURB is the brand identity
// (YouTube + podcast + Discord); DISCORD_BLURB is the server-specific invite.
export const SITE_BLURB =
  "Limited Level-Ups is a YouTube channel, podcast, and Discord community for Magic: The Gathering players who want " +
  "to improve at Limited.\n\nWhether you're looking to get your first trophy, sharpen your fundamentals, or compete " +
  "at the highest level, Limited Level-Ups is here to help you level up your game.";

export const SITE_BLURB_PARAGRAPHS = SITE_BLURB.split("\n\n");

export const DISCORD_BLURB =
  "The Limited Level-Ups Discord is a home for Limited players of all skill levels. Whether you're looking to " +
  "improve your drafting, discuss formats, share your latest trophies, or just chat with other Limited enthusiasts, " +
  "you'll find a welcoming group of players here.";

export interface Host {
  name: string;
  handle: string;
  role: string;
  bio: string;
  photo?: string;
  links: Array<{ label: string; url: string }>;
}

const xAvatar = (handle: string) => `https://unavatar.io/x/${handle}`;

export const HOSTS: Host[] = [
  {
    name: "Alex Nikolic",
    handle: "Chord_O_Calls",
    role: "Host & Founder",
    bio:
      "TBD: Started Limited Level-Ups in 2020 and has hosted every week since — primers, set reviews, draft-alongs, and " +
      "strategy deep-dives on whatever format is live. Also streams drafts on Twitch and coaches.",
    photo: xAvatar("Chord_O_Calls"),
    links: [
      { label: "Twitch", url: SITE_LINKS.twitch },
      { label: "Twitter", url: "https://x.com/Chord_O_Calls" },
    ],
  },
  {
    name: "Marc Anderson",
    handle: "NEO_MTG",
    role: "Set Review co-host",
    bio:
      "TDB: Former National Champion and Face2Face Games pro-team co-founder. Joins Alex for the set-review episodes, " +
      "grading every common and uncommon before each format goes live.",
    photo: xAvatar("NEO_MTG"),
    links: [{ label: "Twitter", url: "https://x.com/NEO_MTG" }],
  },
];

export const HOST = HOSTS[0];

export const LISTEN_ON: Array<{ label: string; url: string }> = [
  { label: "YouTube", url: SITE_LINKS.youtube },
  { label: "Apple", url: SITE_LINKS.apple },
  { label: "Spotify", url: SITE_LINKS.spotify },
  { label: "RSS", url: SITE_LINKS.rss },
];
