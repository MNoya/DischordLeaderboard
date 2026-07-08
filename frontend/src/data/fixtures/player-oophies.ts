import type {
  PlayerDraftEvent,
  PlayerFormatBreakdown,
} from "../../types/leaderboard";

// Real production data for Oophies on SOS, snapshot 2026-05-09.
// Format breakdown aggregated from player_stats; scoreContribution split
// proportionally by trophies until the backend exposes per-format scores.
// Draft events are the most recent 30 from draft_events.

export const oophiesFormatBreakdown: PlayerFormatBreakdown[] = [
  { setCode: "SOS", slug: "oophies", formatLabel: "Trad", events: 67, wins: 144, losses: 57, trophies: 24, scoreContribution: 69.26 },
  { setCode: "SOS", slug: "oophies", formatLabel: "Premier", events: 3, wins: 13, losses: 6, trophies: 1, scoreContribution: 2.89 },
];

export const oophiesDraftEvents: PlayerDraftEvent[] = [
  { slug: "oophies", setCode: "SOS", eventId: "ce67c626-7594-4935-b6af-9d1d411c2376", format: "PremierDraft", expansion: "SOS", wins: 0, losses: 2, isTrophy: false, colors: "WB", startedAt: "2026-05-09T01:47:47Z", finishedAt: "2026-05-09T03:22:22Z", endRank: "Mythic-1" },
  { slug: "oophies", setCode: "SOS", eventId: "83d46444-ceb1-472c-8e11-1f38a9b47ae5", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "UR", startedAt: "2026-05-08T23:10:58Z", finishedAt: "2026-05-09T01:45:31Z", endRank: "Mythic-1" },
  { slug: "oophies", setCode: "SOS", eventId: "a139c569-b8b1-4043-a908-e6e4139f7f18", format: "PremierDraft", expansion: "SOS", wins: 6, losses: 3, isTrophy: false, colors: "WBr", startedAt: "2026-05-08T22:05:09Z", finishedAt: "2026-05-08T23:07:27Z", endRank: "Mythic-1" },
  { slug: "oophies", setCode: "SOS", eventId: "673575c6-66f5-4080-bb20-9dab64e8e002", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "UGbr", startedAt: "2026-05-08T02:36:20Z", finishedAt: "2026-05-08T16:44:54Z", endRank: "Mythic-1" },
  { slug: "oophies", setCode: "SOS", eventId: "f6cc125a-4c56-4af3-be97-4a62cc504cfb", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-05-08T00:40:47Z", finishedAt: "2026-05-08T02:30:49Z", endRank: "Diamond-1" },
  { slug: "oophies", setCode: "SOS", eventId: "ceb89ec6-84b0-499b-bda7-ac7d69c2da92", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "BG", startedAt: "2026-05-07T17:08:01Z", finishedAt: "2026-05-08T00:30:08Z", endRank: "Diamond-1" },
  { slug: "oophies", setCode: "SOS", eventId: "9df2d1f4-3f71-4fa5-9d46-9f1a03b106d1", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-07T15:45:47Z", finishedAt: "2026-05-07T16:34:51Z", endRank: "Diamond-1" },
  { slug: "oophies", setCode: "SOS", eventId: "e0944036-7e22-4d93-afd6-bae7e2c2365e", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-05-07T14:52:17Z", finishedAt: "2026-05-07T15:40:52Z", endRank: "Diamond-1" },
  { slug: "oophies", setCode: "SOS", eventId: "86f307c4-534a-46ae-89dd-9a131167d2e2", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WR", startedAt: "2026-05-06T02:14:56Z", finishedAt: "2026-05-07T14:48:35Z", endRank: "Diamond-1" },
  { slug: "oophies", setCode: "SOS", eventId: "6ddce646-d9dd-4ad0-ab77-61e3818b1f09", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "UG", startedAt: "2026-05-05T18:19:45Z", finishedAt: "2026-05-06T01:03:21Z", endRank: "Diamond-1" },
  { slug: "oophies", setCode: "SOS", eventId: "517c8365-4ae6-4673-a3a2-19b52266aafc", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-05T00:14:52Z", finishedAt: "2026-05-05T17:07:54Z", endRank: "Diamond-1" },
  { slug: "oophies", setCode: "SOS", eventId: "03baf21e-b5a9-4e63-93bf-3d4fdc22a196", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-04T02:44:17Z", finishedAt: "2026-05-04T21:46:57Z", endRank: "Diamond-2" },
  { slug: "oophies", setCode: "SOS", eventId: "c68579c2-94a6-44ec-b9f6-dfda544de0e1", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "URGb", startedAt: "2026-05-03T18:23:24Z", finishedAt: "2026-05-03T19:43:31Z", endRank: "Diamond-2" },
  { slug: "oophies", setCode: "SOS", eventId: "3dad185e-a1a9-42c1-8b62-8056168c807b", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-02T19:00:45Z", finishedAt: "2026-05-02T23:04:28Z", endRank: "Diamond-2" },
  { slug: "oophies", setCode: "SOS", eventId: "c9071f5b-3908-470b-9ef4-9e6d0227288a", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "UGbr", startedAt: "2026-05-02T02:50:32Z", finishedAt: "2026-05-02T15:12:44Z", endRank: "Diamond-2" },
  { slug: "oophies", setCode: "SOS", eventId: "c3984a09-7cdf-4293-b2fc-7da480324a07", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "UR", startedAt: "2026-05-02T01:41:12Z", finishedAt: "2026-05-02T02:44:29Z", endRank: "Diamond-2" },
  { slug: "oophies", setCode: "SOS", eventId: "3cf027d5-6a59-43b4-942b-07e802c93a05", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "BG", startedAt: "2026-05-01T21:39:35Z", finishedAt: "2026-05-01T22:40:51Z", endRank: "Diamond-2" },
  { slug: "oophies", setCode: "SOS", eventId: "72bc2268-4537-43b6-b23f-1678a6eb2d9b", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "BG", startedAt: "2026-05-01T17:14:31Z", finishedAt: "2026-05-01T18:03:30Z", endRank: "Diamond-2" },
  { slug: "oophies", setCode: "SOS", eventId: "920dca41-5c8b-4eb1-9504-73ccbc5018c6", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UG", startedAt: "2026-05-01T15:28:20Z", finishedAt: "2026-05-01T17:13:39Z", endRank: "Diamond-2" },
  { slug: "oophies", setCode: "SOS", eventId: "4ab0467f-f8d7-4dbd-9cf9-3bc1eff64939", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "BG", startedAt: "2026-04-30T16:15:20Z", finishedAt: "2026-04-30T17:11:56Z", endRank: "Diamond-3" },
  { slug: "oophies", setCode: "SOS", eventId: "a0bf7261-18f1-4cd5-b02a-03e0512e7adb", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-04-30T14:43:32Z", finishedAt: "2026-04-30T16:05:35Z", endRank: "Diamond-3" },
  { slug: "oophies", setCode: "SOS", eventId: "10e847c9-4d39-435a-aaa8-092ab7193991", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UG", startedAt: "2026-04-29T22:54:40Z", finishedAt: "2026-04-30T03:16:40Z", endRank: "Diamond-3" },
  { slug: "oophies", setCode: "SOS", eventId: "7e682a77-8224-419e-8cb7-b307324d1383", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UR", startedAt: "2026-04-29T21:08:13Z", finishedAt: "2026-04-29T22:41:38Z", endRank: "Diamond-3" },
  { slug: "oophies", setCode: "SOS", eventId: "23ae1263-616b-48f9-850a-d0e9e3743aae", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "BG", startedAt: "2026-04-29T16:00:25Z", finishedAt: "2026-04-29T17:18:36Z", endRank: "Diamond-3" },
  { slug: "oophies", setCode: "SOS", eventId: "177eb2d6-4927-461a-afc8-55fff9fa28c6", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UGbr", startedAt: "2026-04-29T14:16:31Z", finishedAt: "2026-04-29T15:12:30Z", endRank: "Diamond-3" },
  { slug: "oophies", setCode: "SOS", eventId: "2e8f00a9-0235-4afd-9084-7edd695260fb", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "URwbg", startedAt: "2026-04-29T02:07:26Z", finishedAt: "2026-04-29T14:02:48Z", endRank: "Diamond-3" },
  { slug: "oophies", setCode: "SOS", eventId: "716a7ef0-4d78-4ab1-9ac6-c33c6f8a8355", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-04-29T00:37:57Z", finishedAt: "2026-04-29T01:24:54Z", endRank: "Diamond-4" },
  { slug: "oophies", setCode: "SOS", eventId: "51f9e541-f2f6-4488-8246-00ba5fe7f587", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "UR", startedAt: "2026-04-28T21:13:09Z", finishedAt: "2026-04-28T22:38:48Z", endRank: "Diamond-4" },
  { slug: "oophies", setCode: "SOS", eventId: "ea9c29c6-e6d5-4b7a-bad1-d8ab36ceea10", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "URwbg", startedAt: "2026-04-28T17:39:22Z", finishedAt: "2026-04-28T19:08:26Z", endRank: "Diamond-4" },
  { slug: "oophies", setCode: "SOS", eventId: "f4ce596b-b8b0-4fab-8f41-e7a65587dfb9", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "BG", startedAt: "2026-04-28T16:48:34Z", finishedAt: "2026-04-28T17:22:41Z", endRank: "Diamond-4" },
];
