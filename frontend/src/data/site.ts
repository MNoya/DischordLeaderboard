// Single source of truth for the community site's static content — external
// links, host bio, support tiers, show-format legend, and the off-site
// platforms. Pages and the footer read from here so a copy or URL change
// cascades everywhere instead of being duplicated per page.

export const SITE_LINKS = {
  discord: "https://discord.com/invite/XWNVT9mxvU",
  patreon: "https://patreon.com/limitedlevelups",
  github: "https://github.com/mnoya/DischordLeaderboard",
  seventeenLands: "https://www.17lands.com",
  podcast: "https://limitedlevelups.libsyn.com",
  youtube: "https://www.youtube.com/@limitedlevel-ups",
  twitch: "https://www.twitch.tv/chord_o_calls",
  bluesky: "https://bsky.app/profile/limitedlevelups.bsky.social",
  reddit: "https://www.reddit.com/r/limitedlevelups",
  apple: "https://podcasts.apple.com/podcast/limited-level-ups",
  spotify: "https://open.spotify.com/show/limited-level-ups",
  rss: "https://feeds.libsyn.com/limitedlevelups/rss",
  mailbag: "mailto:hello@limitedlevelups.com",
} as const;

export const DISCORD_GUILD_ID = "775371722065051658";

export function discordEventLink(eventId: string): string {
  return `https://discord.com/events/${DISCORD_GUILD_ID}/${eventId}`;
}

export const SITE_TAGLINE = "Get better at draft. One set at a time.";

export const SITE_PITCH =
  "Every format, covered from first impressions through sunset. Primers, set reviews, draft-alongs — straight talk for players who want to level up.";

export const SITE_STATS: Array<{ value: string; label: string }> = [
  { value: "240+", label: "Episodes" },
  { value: "16", label: "Sets covered" },
  { value: "5+ yrs", label: "Since 2020" },
  { value: "4.2k", label: "Discord members" },
];

export const SHOW_FORMAT: Array<{ name: string; blurb: string }> = [
  { name: "Set Primer", blurb: "Release-week overview" },
  { name: "Set Review", blurb: "Commons / uncommons / rares" },
  { name: "Draft-along", blurb: "Pick-by-pick breakdown" },
  { name: "Strategy", blurb: "Evergreen skill topics" },
  { name: "Sunset Show", blurb: "Format farewell" },
];

export const HOST = {
  name: "Alex",
  handle: "Chord_O_Calls",
  bio: "Host since 2020. Drafts every format, writes deep dives on archetypes and signals, has strong opinions about mana bases. Also streams on Twitch and runs pod drafts on Discord most weekends.",
  socials: [
    { label: "YouTube", url: SITE_LINKS.youtube },
    { label: "Twitch", url: SITE_LINKS.twitch },
    { label: "Bluesky", url: SITE_LINKS.bluesky },
  ],
};

export const SUPPORT_TIERS: Array<{
  name: string;
  price: string;
  perks: string[];
  cta: string;
  featured?: boolean;
}> = [
  {
    name: "Drafter",
    price: "$3",
    perks: ["Ad-free feed", "Patron-only Discord role", "Early episode access (24h)"],
    cta: "Become a Drafter",
  },
  {
    name: "Deckbuilder",
    price: "$7",
    perks: [
      "Everything in Drafter",
      "Monthly bonus episode",
      "Private #patron-drafts channel",
      "Name in episode credits",
    ],
    cta: "Most popular",
    featured: true,
  },
  {
    name: "Mythic",
    price: "$20",
    perks: [
      "Everything in Deckbuilder",
      "Quarterly group draft w/ hosts",
      "Submit questions to bonus mailbag",
      "Signed swag once a year",
    ],
    cta: "Become a Mythic",
  },
];

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
    blurb: "Video version of every episode, plus draft-along gameplay clips and guest interviews that don't make the audio feed.",
    stat: "14.2k subscribers · new video weekly",
    action: "Subscribe",
    url: SITE_LINKS.youtube,
  },
  {
    key: "twitch",
    name: "Twitch",
    blurb: "Live drafts, co-streams during Pro Tours, and the occasional listener Q&A stream.",
    stat: "Streaming 2× per week",
    action: "Follow",
    url: SITE_LINKS.twitch,
  },
  {
    key: "bluesky",
    name: "Bluesky",
    blurb: "Hot takes, spoiler reactions, episode drops. Short-form and fast-moving.",
    stat: "@limitedlevelups.bsky.social",
    action: "Follow",
    url: SITE_LINKS.bluesky,
  },
  {
    key: "reddit",
    name: "Subreddit",
    blurb: "Longer-form discussion threads, draft pool deckbuilding help, episode commentary.",
    stat: "r/limitedlevelups · 1.1k readers",
    action: "Visit",
    url: SITE_LINKS.reddit,
  },
  {
    key: "patreon",
    name: "Patreon",
    blurb: "The show is listener-supported. Backers get bonus episodes, early access, ad-free feeds, and a private Discord channel.",
    stat: "From $3/month",
    action: "Become a patron",
    url: SITE_LINKS.patreon,
  },
];

export const LISTEN_ON: Array<{ label: string; url: string }> = [
  { label: "Apple", url: SITE_LINKS.apple },
  { label: "Spotify", url: SITE_LINKS.spotify },
  { label: "YouTube", url: SITE_LINKS.youtube },
  { label: "RSS", url: SITE_LINKS.rss },
];
