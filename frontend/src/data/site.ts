// Single source of truth for the community site's static content — external
// links, the mission blurbs, hosts, show-format legend, and the off-site
// platforms. Pages and the footer read from here so a copy or URL change
// cascades everywhere instead of being duplicated per page.
//
// Counts here are verified snapshots; bump them when they drift. The Discord
// member count and the episode count render live (invite API + RSS feed).

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

export const SITE_TAGLINE = "Level up your Limited game.";

export const SITE_BLURB =
  "Limited Level-Ups is a YouTube channel, podcast, and Discord community for Magic: The Gathering players who want " +
  "to improve at Limited. Whether you're chasing your first trophy, sharpening your fundamentals, or competing at " +
  "the highest level, Limited Level-Ups is here to help you level up your game.";

export const DISCORD_BLURB =
  "A home for Limited players of all skill levels. Whether you want to improve your drafting, discuss formats, share " +
  "your latest trophies, or just chat with other Limited enthusiasts, you'll find a welcoming group of players here.";

export const COMMUNITY_STATS = {
  youtubeSubscribers: "17K",
  patreonSupporters: "918",
  sinceYear: "2020",
} as const;

export const SHOW_FORMAT: Array<{ name: string; blurb: string }> = [
  { name: "Set Review", blurb: "Release-week takes & card grades" },
  { name: "Draft", blurb: "Pick-by-pick breakdown" },
  { name: "Sealed", blurb: "Prerelease & sealed prep" },
  { name: "Rankings", blurb: "Top 10s & tier lists" },
  { name: "Metagame", blurb: "Per-set meta & format updates" },
  { name: "Coaching", blurb: "Leveling up players through real drafts" },
  { name: "Guest", blurb: "Interviews & conversations with pros" },
  { name: "Evergreen", blurb: "Timeless skills, retros & extras" },
];

export interface Host {
  name: string;
  handle: string;
  role: string;
  bio: string;
  links: Array<{ label: string; url: string }>;
}

export const HOSTS: Host[] = [
  {
    name: "Alex Nikolic",
    handle: "Chord_O_Calls",
    role: "Host & Founder",
    bio:
      "Started Limited Level-Ups in 2020 and has hosted every week since — primers, set reviews, draft-alongs, and " +
      "strategy deep-dives on whatever format is live. Also streams drafts on Twitch and coaches.",
    links: [
      { label: "Twitch", url: SITE_LINKS.twitch },
      { label: "YouTube", url: SITE_LINKS.youtube },
    ],
  },
  {
    name: "Marc Anderson",
    handle: "NEO_MTG",
    role: "Set Review co-host",
    bio:
      "Former National Champion and Face2Face Games pro-team co-founder. Joins Alex for the set-review episodes, " +
      "grading every common and uncommon before each format goes live.",
    links: [{ label: "Twitter", url: "https://x.com/NEO_MTG" }],
  },
];

export const HOST = HOSTS[0];

export const COMMUNITY_PLATFORMS: Array<{
  key: string;
  name: string;
  blurb: string;
  stat: string;
  action: string;
  url: string;
}> = [
  {
    key: "youtube",
    name: "YouTube",
    blurb: "Every episode in video, plus draft-along gameplay and guest sessions that don't make the audio feed.",
    stat: `${COMMUNITY_STATS.youtubeSubscribers} subscribers`,
    action: "Subscribe",
    url: SITE_LINKS.youtube,
  },
  {
    key: "podcast",
    name: "Podcast",
    blurb: "Listen on Apple, Spotify, or any podcast app — a new deep-dive episode most weeks.",
    stat: `Since ${COMMUNITY_STATS.sinceYear}`,
    action: "Listen",
    url: SITE_LINKS.apple,
  },
  {
    key: "twitch",
    name: "Twitch",
    blurb: "Live drafts and ladder runs with Alex, plus the occasional listener Q&A stream.",
    stat: "twitch.tv/chord_o_calls",
    action: "Follow",
    url: SITE_LINKS.twitch,
  },
  {
    key: "patreon",
    name: "Patreon",
    blurb: "The show is listener-supported. Back it to help keep new episodes coming every week.",
    stat: `${COMMUNITY_STATS.patreonSupporters} supporters · from $4/mo`,
    action: "Become a patron",
    url: SITE_LINKS.patreon,
  },
];

export const LISTEN_ON: Array<{ label: string; url: string }> = [
  { label: "YouTube", url: SITE_LINKS.youtube },
  { label: "Apple", url: SITE_LINKS.apple },
  { label: "Spotify", url: SITE_LINKS.spotify },
  { label: "RSS", url: SITE_LINKS.rss },
];
