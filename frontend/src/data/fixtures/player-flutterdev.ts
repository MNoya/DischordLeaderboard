import type {
  PlayerDraftEvent,
  PlayerFormatBreakdown,
} from "../../types/leaderboard";

// Real production data for flutterdev on SOS, snapshot 2026-05-09.
// Format breakdown aggregated from player_stats; scoreContribution split
// proportionally by trophies until the backend exposes per-format scores.
// Draft events are the most recent 30 from draft_events.

export const flutterdevFormatBreakdown: PlayerFormatBreakdown[] = [
  { setCode: "SOS", slug: "flutterdev", formatLabel: "Premier", events: 41, wins: 206, losses: 92, trophies: 14, scoreContribution: 50.55 },
  { setCode: "SOS", slug: "flutterdev", formatLabel: "Trad", events: 7, wins: 18, losses: 0, trophies: 6, scoreContribution: 21.67 },
];

export const flutterdevDraftEvents: PlayerDraftEvent[] = [
  { slug: "flutterdev", setCode: "SOS", eventId: "c450201c-ac9b-4af5-8fbc-20d67949aa29", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WR", startedAt: "2026-05-08T16:09:20Z", finishedAt: "2026-05-08T16:09:36Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "6252745c-6e7c-4976-9384-99b17b0cf98a", format: "PremierDraft", expansion: "SOS", wins: 1, losses: 3, isTrophy: false, colors: "WBr", startedAt: "2026-05-07T23:02:38Z", finishedAt: "2026-05-07T23:45:25Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "28a8ea40-b57e-4d7e-aa72-ce99618af968", format: "PremierDraft", expansion: "SOS", wins: 6, losses: 3, isTrophy: false, colors: "UGr", startedAt: "2026-05-07T20:42:53Z", finishedAt: "2026-05-07T20:43:50Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "0ddfbc06-609c-47b5-8bdd-9c2195aff351", format: "PremierDraft", expansion: "SOS", wins: 2, losses: 3, isTrophy: false, colors: "WB", startedAt: "2026-05-07T20:42:19Z", finishedAt: "2026-05-07T20:42:52Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "c551c26b-c413-4f7b-bdf5-3e7532fc2bc0", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-05-07T09:14:50Z", finishedAt: "2026-05-07T09:15:24Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "5fee4d2e-481b-4191-a51c-228ae179f106", format: "PremierDraft", expansion: "SOS", wins: 6, losses: 3, isTrophy: false, colors: "UR", startedAt: "2026-05-07T06:51:35Z", finishedAt: "2026-05-07T06:52:38Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "a368daf8-d139-43c0-9af2-eb40c431860e", format: "PremierDraft", expansion: "SOS", wins: 5, losses: 3, isTrophy: false, colors: "URg", startedAt: "2026-05-07T06:50:54Z", finishedAt: "2026-05-07T06:51:35Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "3fef9248-7346-4c95-aac4-6fd5f835129a", format: "PremierDraft", expansion: "SOS", wins: 4, losses: 3, isTrophy: false, colors: "WRu", startedAt: "2026-05-06T19:34:12Z", finishedAt: "2026-05-06T20:36:25Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "e51bc8e5-b725-4cb6-bd92-85d0ba9c0a45", format: "PremierDraft", expansion: "SOS", wins: 3, losses: 3, isTrophy: false, colors: "WRu", startedAt: "2026-05-06T18:16:27Z", finishedAt: "2026-05-06T19:33:43Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "276a1508-29d3-4a46-b8c5-62c42d3dcca0", format: "PremierDraft", expansion: "SOS", wins: 6, losses: 3, isTrophy: false, colors: "WR", startedAt: "2026-05-06T16:45:00Z", finishedAt: "2026-05-06T18:13:16Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "e3c7eb55-8c0e-46f7-b29e-044764182d3d", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "WR", startedAt: "2026-05-06T16:22:08Z", finishedAt: "2026-05-06T16:22:42Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "79eac96f-7650-405a-b73f-d7fee2c27819", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 2, isTrophy: true, colors: "WRu", startedAt: "2026-05-06T00:42:20Z", finishedAt: "2026-05-06T00:43:19Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "5ae7b218-56d6-4e35-8442-9d42ecd3d775", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-05-05T16:29:41Z", finishedAt: "2026-05-05T16:30:16Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "5dea6a20-22cc-4b1a-bb3e-d8d20387d5ce", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "WR", startedAt: "2026-05-05T05:30:59Z", finishedAt: "2026-05-05T05:33:31Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "07527be2-c8c5-4ba7-a333-c03bbd7777ce", format: "PremierDraft", expansion: "SOS", wins: 5, losses: 3, isTrophy: false, colors: "WR", startedAt: "2026-05-04T04:40:12Z", finishedAt: "2026-05-04T05:41:31Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "af4cad9a-057d-43a8-89e2-7c7e906167f0", format: "PremierDraft", expansion: "SOS", wins: 6, losses: 3, isTrophy: false, colors: "WR", startedAt: "2026-05-04T02:17:07Z", finishedAt: "2026-05-04T03:46:18Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "36334687-9e02-4681-ac03-4551aef5aaa2", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-05-04T02:15:50Z", finishedAt: "2026-05-04T02:16:29Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "efb44156-b50d-4e92-ab4e-8e762b25f99e", format: "PremierDraft", expansion: "SOS", wins: 4, losses: 3, isTrophy: false, colors: "URw", startedAt: "2026-05-04T02:15:06Z", finishedAt: "2026-05-04T02:15:49Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "18114815-0a2b-4849-8172-667069e0517c", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 2, isTrophy: true, colors: "WR", startedAt: "2026-05-03T19:13:16Z", finishedAt: "2026-05-03T20:33:47Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "3f07dd40-e3a3-456b-bf66-e9128193ef77", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 2, isTrophy: true, colors: "WR", startedAt: "2026-05-03T19:08:31Z", finishedAt: "2026-05-03T19:09:14Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "93a02d3f-9214-40fe-bc1b-684ce49e729b", format: "PremierDraft", expansion: "SOS", wins: 1, losses: 3, isTrophy: false, colors: "UBg", startedAt: "2026-05-03T19:07:56Z", finishedAt: "2026-05-03T19:08:30Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "8c0ecf1f-a83f-481d-b160-fb8b39d9eaee", format: "PremierDraft", expansion: "SOS", wins: 2, losses: 3, isTrophy: false, colors: "WR", startedAt: "2026-05-03T19:07:18Z", finishedAt: "2026-05-03T19:07:55Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "7d428cb1-7584-4ac3-9897-af47a1eab3da", format: "PremierDraft", expansion: "SOS", wins: 5, losses: 3, isTrophy: false, colors: "WR", startedAt: "2026-05-03T04:19:28Z", finishedAt: "2026-05-03T04:20:18Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "e1d6983f-548f-4309-a794-b6337722be98", format: "PremierDraft", expansion: "SOS", wins: 5, losses: 3, isTrophy: false, colors: "URwbg", startedAt: "2026-05-03T04:18:37Z", finishedAt: "2026-05-03T04:19:27Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "77c497ec-fec8-406a-bf5e-1bb599548594", format: "PremierDraft", expansion: "SOS", wins: 5, losses: 3, isTrophy: false, colors: "WR", startedAt: "2026-05-03T04:17:56Z", finishedAt: "2026-05-03T04:18:36Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "841a2f6a-e595-487a-8ce0-dba3d397cda2", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-05-01T17:26:17Z", finishedAt: "2026-05-01T18:11:45Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "86493cb5-9cb2-40f8-b31c-083be31c1dde", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "URw", startedAt: "2026-04-30T20:04:20Z", finishedAt: "2026-04-30T20:04:57Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "15fac11c-0a2d-4762-a257-94d058e8271a", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WR", startedAt: "2026-04-30T02:31:57Z", finishedAt: "2026-04-30T02:33:37Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "6d82ac0c-db11-4fff-8c8c-7a2376fcbbf6", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 0, isTrophy: true, colors: "URwbg", startedAt: "2026-04-29T03:19:21Z", finishedAt: "2026-04-29T03:20:13Z" },
  { slug: "flutterdev", setCode: "SOS", eventId: "d166703a-4db0-4a26-80b7-75f2992dcd03", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 0, isTrophy: true, colors: "WR", startedAt: "2026-04-29T00:20:13Z", finishedAt: "2026-04-29T00:20:51Z" },
];
