import type {
  PlayerDraftEvent,
  PlayerFormatBreakdown,
} from "../../types/leaderboard";

// Real production data for Elfandor on SOS, snapshot 2026-05-09.
// Format breakdown aggregated from player_stats; scoreContribution split
// proportionally by trophies until the backend exposes per-format scores.
// Draft events are the most recent 30 from draft_events.

export const elfandorFormatBreakdown: PlayerFormatBreakdown[] = [
  { setCode: "SOS", slug: "elfandor", formatLabel: "Premier", events: 57, wins: 258, losses: 138, trophies: 18, scoreContribution: 41.55 },
  { setCode: "SOS", slug: "elfandor", formatLabel: "Arena Direct", events: 46, wins: 162, losses: 80, trophies: 10, scoreContribution: 23.08 },
  { setCode: "SOS", slug: "elfandor", formatLabel: "Trad", events: 8, wins: 18, losses: 6, trophies: 3, scoreContribution: 6.93 },
];

export const elfandorDraftEvents: PlayerDraftEvent[] = [
  { slug: "elfandor", setCode: "SOS", eventId: "205559bd-32d2-4697-8ca1-d23a8984d38c", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WRu", startedAt: "2026-05-08T22:42:51Z", finishedAt: "2026-05-09T00:08:12Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "a5d72ee2-e199-4f66-bd94-42a5f4ac1973", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WR", startedAt: "2026-05-08T17:59:42Z", finishedAt: "2026-05-08T19:18:58Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "1d55b19a-975d-45b9-864f-334757fd4254", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-08T14:45:04Z", finishedAt: "2026-05-08T15:41:35Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "bbfd255c-d4ec-4cec-9e05-2fed92aa78b6", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 2, isTrophy: true, colors: "UR", startedAt: "2026-05-07T10:07:45Z", finishedAt: "2026-05-07T11:40:20Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "8847104a-c117-41d5-9e65-fccfa94669f1", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 0, isTrophy: true, colors: "URGwb", startedAt: "2026-05-07T08:40:46Z", finishedAt: "2026-05-07T09:54:56Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "c697310e-836c-4235-b6cd-b6c38bb969c9", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 2, isTrophy: true, colors: "WB", startedAt: "2026-05-06T21:08:18Z", finishedAt: "2026-05-06T23:36:40Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "837ac413-0f69-496e-a5c1-7af08bb2f8c3", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "WRu", startedAt: "2026-05-06T12:49:20Z", finishedAt: "2026-05-06T14:11:47Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "210fa8a7-d9a2-419d-bc34-d668e199de9e", format: "PremierDraft", expansion: "SOS", wins: 4, losses: 3, isTrophy: false, colors: "URGb", startedAt: "2026-05-06T11:14:05Z", finishedAt: "2026-05-06T12:48:08Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "43529773-3b3c-43dd-a4a5-23bf778c994a", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "UR", startedAt: "2026-05-06T08:51:37Z", finishedAt: "2026-05-06T10:22:16Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "8a88dcc3-7f21-4b2c-9b55-79bea21b3977", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "BG", startedAt: "2026-05-05T20:01:51Z", finishedAt: "2026-05-05T21:03:07Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "1ab929f6-c6f5-44bb-9564-b56c2bf896b1", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "BGu", startedAt: "2026-05-05T17:42:26Z", finishedAt: "2026-05-05T18:37:37Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "86c143fb-4e7d-488e-bd5c-e6338d9d8f3a", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WB", startedAt: "2026-05-05T16:31:21Z", finishedAt: "2026-05-05T17:40:07Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "3797690c-1d3a-406a-9145-3c9280370fff", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "BG", startedAt: "2026-05-05T12:24:52Z", finishedAt: "2026-05-05T13:42:46Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "a28c2e4f-a241-4232-b46d-ed38e7cc7529", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-05T10:41:36Z", finishedAt: "2026-05-05T12:23:56Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "0ed5e64d-ce25-4c2b-a5ec-93706065ee0c", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "WB", startedAt: "2026-05-04T21:00:03Z", finishedAt: "2026-05-05T10:35:27Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "d35c92ad-2a31-4951-9959-32305e55dcf9", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "UR", startedAt: "2026-05-03T21:37:31Z", finishedAt: "2026-05-03T23:00:34Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "d016087f-3cc8-43ee-8bd0-290a604ab46d", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 5, losses: 2, isTrophy: false, colors: "WURbg", startedAt: "2026-05-03T20:39:06Z", finishedAt: "2026-05-03T21:31:39Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "3ff5d572-7300-4925-b7b9-db77ce95669d", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 0, losses: 2, isTrophy: false, colors: "WUR", startedAt: "2026-05-03T16:51:02Z", finishedAt: "2026-05-03T20:26:04Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "5cb3b077-9081-4ffe-a6ad-f72647107cd6", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WBr", startedAt: "2026-05-03T16:05:22Z", finishedAt: "2026-05-03T16:44:31Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "2ab4a1ec-3a93-4b15-9c79-192d05d582b9", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 0, losses: 2, isTrophy: false, colors: "WUR", startedAt: "2026-05-03T14:27:02Z", finishedAt: "2026-05-03T16:02:17Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "a7ac4ecd-43e6-4062-8d03-2002249ade90", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "UG", startedAt: "2026-05-03T13:48:45Z", finishedAt: "2026-05-03T14:20:09Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "27bc5ba0-b5dc-48d4-b2d9-b93b8c373204", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 2, losses: 2, isTrophy: false, colors: "WR", startedAt: "2026-05-03T13:16:18Z", finishedAt: "2026-05-03T13:42:42Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "59f4f60b-68dc-4601-8ce2-e98c2d45d927", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "URwg", startedAt: "2026-05-03T10:45:10Z", finishedAt: "2026-05-03T11:52:02Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "f2141ec4-6476-4ca2-bf5d-0512e74fe2cc", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 0, losses: 2, isTrophy: false, colors: "URg", startedAt: "2026-05-03T10:22:43Z", finishedAt: "2026-05-03T10:39:25Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "4926f7af-a6af-4d50-9a76-efac9b8faf7b", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 4, losses: 2, isTrophy: false, colors: "WB", startedAt: "2026-05-03T09:06:18Z", finishedAt: "2026-05-03T09:53:28Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "cf2b4be5-afed-4a46-b9f5-0f48ba039031", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 4, losses: 2, isTrophy: false, colors: "UGbr", startedAt: "2026-05-03T08:06:11Z", finishedAt: "2026-05-03T09:02:38Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "eccb8544-78ed-4d30-8052-a51fe97c529d", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 7, losses: 1, isTrophy: true, colors: "WRu", startedAt: "2026-05-02T19:26:16Z", finishedAt: "2026-05-02T22:07:09Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "b159d6d4-b0fc-4c9a-ba7d-f109d901b3d8", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 0, losses: 2, isTrophy: false, colors: "URw", startedAt: "2026-05-02T19:03:57Z", finishedAt: "2026-05-02T19:19:33Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "d71be82b-f8fa-48e8-8034-87777e8a29ba", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 6, losses: 2, isTrophy: false, colors: "UR", startedAt: "2026-05-02T17:35:44Z", finishedAt: "2026-05-02T18:53:41Z" },
  { slug: "elfandor", setCode: "SOS", eventId: "3e6ef6f3-05b6-4868-80c7-48ca07b1eda4", format: "ArenaDirect_Sealed", expansion: "SOS", wins: 7, losses: 0, isTrophy: true, colors: "WRb", startedAt: "2026-05-02T16:14:18Z", finishedAt: "2026-05-02T17:32:07Z" },
];
