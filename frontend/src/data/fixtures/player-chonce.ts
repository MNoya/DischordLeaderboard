import type { PlayerDraftEvent, PlayerFormatBreakdown } from "../../types/leaderboard";

// Featured player: Chonce — rank 10 on SOS, 28.39 score, 12 trophies, 49 events.
// Chosen for breadth (mixes Trad-heavy with Premier and a few Quick / Sealed events).
// scoreContribution split proportionally by trophies (9 of 12 in Trad; 3 in Premier).
export const chonceFormatBreakdown: PlayerFormatBreakdown[] = [
  { setCode: "SOS", slug: "chonce", formatLabel: "Trad",        events: 23, wins: 50, losses: 18, trophies: 9, scoreContribution: 21.29 },
  { setCode: "SOS", slug: "chonce", formatLabel: "Premier",     events: 22, wins: 73, losses: 62, trophies: 3, scoreContribution: 7.10  },
  { setCode: "SOS", slug: "chonce", formatLabel: "Quick",       events: 2,  wins: 9,  losses: 6,  trophies: 0, scoreContribution: 0     },
  { setCode: "SOS", slug: "chonce", formatLabel: "Sealed",      events: 1,  wins: 4,  losses: 3,  trophies: 0, scoreContribution: 0     },
  { setCode: "SOS", slug: "chonce", formatLabel: "Trad Sealed", events: 1,  wins: 3,  losses: 2,  trophies: 0, scoreContribution: 0     },
];

// All 49 SOS events for Chonce, finished_at DESC. `colors` preserved verbatim from
// 17lands: uppercase = main, lowercase = splash. E.g. 'URg' = UR with green splash.
export const chonceDraftEvents: PlayerDraftEvent[] = [
  { slug: "chonce", setCode: "SOS", eventId: "2c95a0e8-f3b4-43f4-a3d8-fd5c65d236c5", format: "TradDraft",    expansion: "SOS", wins: 1, losses: 1, isTrophy: false, colors: "BG",   startedAt: "2026-05-08T00:59:18Z", finishedAt: "2026-05-08T01:38:47Z" },
  { slug: "chonce", setCode: "SOS", eventId: "375a394d-4cd1-4093-b32b-6af18075c488", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WR",   startedAt: "2026-05-07T23:17:09Z", finishedAt: "2026-05-08T00:54:49Z" },
  { slug: "chonce", setCode: "SOS", eventId: "936aa101-f296-4f9c-a477-1173939222f9", format: "TradDraft",    expansion: "SOS", wins: 3, losses: 0, isTrophy: true,  colors: "URg",  startedAt: "2026-05-07T22:19:13Z", finishedAt: "2026-05-07T23:14:41Z" },
  { slug: "chonce", setCode: "SOS", eventId: "1f030288-b732-4b42-a40f-3420c0c5d7a5", format: "PremierDraft", expansion: "SOS", wins: 4, losses: 3, isTrophy: false, colors: "URwg", startedAt: "2026-05-05T23:20:42Z", finishedAt: "2026-05-07T21:59:13Z" },
  { slug: "chonce", setCode: "SOS", eventId: "77c2435c-40ac-46e1-8656-12b466182ca2", format: "PremierDraft", expansion: "SOS", wins: 4, losses: 3, isTrophy: false, colors: "UR",   startedAt: "2026-05-04T01:37:25Z", finishedAt: "2026-05-05T23:19:23Z" },
  { slug: "chonce", setCode: "SOS", eventId: "5ce1765d-e9ee-41a2-a7ba-fec01210c5e1", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 1, isTrophy: true,  colors: "WR",   startedAt: "2026-05-03T15:38:32Z", finishedAt: "2026-05-04T01:36:13Z" },
  { slug: "chonce", setCode: "SOS", eventId: "658d3e99-b5f9-4f5d-ba14-9ff4839b8e9e", format: "PremierDraft", expansion: "SOS", wins: 3, losses: 3, isTrophy: false, colors: "BG",   startedAt: "2026-05-03T02:22:44Z", finishedAt: "2026-05-03T15:38:09Z" },
  { slug: "chonce", setCode: "SOS", eventId: "107f14fb-b839-4c3f-9972-1263cbb8041a", format: "TradDraft",    expansion: "SOS", wins: 3, losses: 0, isTrophy: true,  colors: "UGb",  startedAt: "2026-05-03T01:16:57Z", finishedAt: "2026-05-03T02:20:41Z" },
  { slug: "chonce", setCode: "SOS", eventId: "ecb20b32-b7d5-41dd-b112-b46a895c4640", format: "PremierDraft", expansion: "SOS", wins: 7, losses: 2, isTrophy: true,  colors: "BG",   startedAt: "2026-05-01T23:36:35Z", finishedAt: "2026-05-02T15:29:03Z" },
  { slug: "chonce", setCode: "SOS", eventId: "e0b4e2c2-ef8c-43a9-8a09-e5a5bbcd99b7", format: "PremierDraft", expansion: "SOS", wins: 0, losses: 3, isTrophy: false, colors: "UGb",  startedAt: "2026-05-01T23:17:09Z", finishedAt: "2026-05-01T23:36:16Z" },
  { slug: "chonce", setCode: "SOS", eventId: "bbd94128-0e01-4771-b56f-4ff0f8429e36", format: "PremierDraft", expansion: "SOS", wins: 3, losses: 3, isTrophy: false, colors: "BGu",  startedAt: "2026-05-01T01:47:42Z", finishedAt: "2026-05-01T22:51:20Z" },
  { slug: "chonce", setCode: "SOS", eventId: "3d9cf5f1-2b92-4565-b2c7-a786148db228", format: "QuickDraft",   expansion: "SOS", wins: 4, losses: 3, isTrophy: false, colors: "WB",   startedAt: "2026-05-01T22:06:11Z", finishedAt: "2026-05-01T22:46:28Z" },
  { slug: "chonce", setCode: "SOS", eventId: "96c6940e-3879-42a0-af34-fa901a4ad83f", format: "PremierDraft", expansion: "SOS", wins: 1, losses: 3, isTrophy: false, colors: "WR",   startedAt: "2026-04-30T00:26:52Z", finishedAt: "2026-05-01T01:47:16Z" },
  { slug: "chonce", setCode: "SOS", eventId: "b591635a-f399-4dab-9b8a-aa96d4e58ca3", format: "QuickDraft",   expansion: "SOS", wins: 5, losses: 3, isTrophy: false, colors: "WB",   startedAt: "2026-05-01T00:40:12Z", finishedAt: "2026-05-01T01:20:10Z" },
  { slug: "chonce", setCode: "SOS", eventId: "9a1f7c3a-9f69-4804-a8db-3f4d700ffaf8", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UR",   startedAt: "2026-04-29T21:43:35Z", finishedAt: "2026-04-30T00:25:22Z" },
  { slug: "chonce", setCode: "SOS", eventId: "a2673d81-5e50-4faa-bf61-0b6a78ca7b96", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB",   startedAt: "2026-04-29T20:52:07Z", finishedAt: "2026-04-29T21:41:01Z" },
  { slug: "chonce", setCode: "SOS", eventId: "5d76f3be-cec8-4f61-92a8-524771bfde14", format: "TradDraft",    expansion: "SOS", wins: 3, losses: 0, isTrophy: true,  colors: "WB",   startedAt: "2026-04-29T19:46:35Z", finishedAt: "2026-04-29T20:46:11Z" },
  { slug: "chonce", setCode: "SOS", eventId: "22ab41db-bba8-4702-bdf5-6ff03b681a9f", format: "TradDraft",    expansion: "SOS", wins: 3, losses: 0, isTrophy: true,  colors: "URb",  startedAt: "2026-04-29T18:14:44Z", finishedAt: "2026-04-29T19:43:28Z" },
  { slug: "chonce", setCode: "SOS", eventId: "e89520e7-d50b-42cc-bd2c-02d7a79c14dc", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "URg",  startedAt: "2026-04-28T22:02:57Z", finishedAt: "2026-04-29T18:11:45Z" },
  { slug: "chonce", setCode: "SOS", eventId: "28ad7b21-8b1c-4616-976a-7f064607c1ff", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UR",   startedAt: "2026-04-28T02:00:27Z", finishedAt: "2026-04-28T22:01:57Z" },
  { slug: "chonce", setCode: "SOS", eventId: "9e706ddc-8cd9-4b01-8c62-32ed902a5297", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WR",   startedAt: "2026-04-28T00:02:03Z", finishedAt: "2026-04-28T01:07:22Z" },
  { slug: "chonce", setCode: "SOS", eventId: "9407fe4c-109e-420f-8d6e-78625092cbb2", format: "TradDraft",    expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WB",   startedAt: "2026-04-27T22:49:54Z", finishedAt: "2026-04-27T23:55:09Z" },
  { slug: "chonce", setCode: "SOS", eventId: "2bbbd553-a04b-4049-bb25-fcf93bf11263", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UBRG", startedAt: "2026-04-27T21:46:36Z", finishedAt: "2026-04-27T22:47:58Z" },
  { slug: "chonce", setCode: "SOS", eventId: "f32b4b78-49c5-4a30-be84-323790c957c3", format: "TradDraft",    expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WBr",  startedAt: "2026-04-26T23:56:34Z", finishedAt: "2026-04-27T01:30:06Z" },
  { slug: "chonce", setCode: "SOS", eventId: "4e31d44e-e9ff-4355-a5dc-1d7c4247f477", format: "TradDraft",    expansion: "SOS", wins: 3, losses: 0, isTrophy: true,  colors: "WB",   startedAt: "2026-04-26T20:12:12Z", finishedAt: "2026-04-26T23:37:19Z" },
  { slug: "chonce", setCode: "SOS", eventId: "b0b13562-75e4-4971-86c3-613dee7cb458", format: "TradDraft",    expansion: "SOS", wins: 3, losses: 0, isTrophy: true,  colors: "WR",   startedAt: "2026-04-26T16:52:37Z", finishedAt: "2026-04-26T20:04:15Z" },
  { slug: "chonce", setCode: "SOS", eventId: "afe57606-1f06-45b6-83ec-3371938e6ae5", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UR",   startedAt: "2026-04-26T14:32:39Z", finishedAt: "2026-04-26T16:50:43Z" },
  { slug: "chonce", setCode: "SOS", eventId: "8ba554ac-d025-4ce0-ac8c-ca30f74884b0", format: "TradDraft",    expansion: "SOS", wins: 3, losses: 0, isTrophy: true,  colors: "BG",   startedAt: "2026-04-26T13:30:26Z", finishedAt: "2026-04-26T14:29:55Z" },
  { slug: "chonce", setCode: "SOS", eventId: "bdba096a-8a33-4724-83db-3ba11d867980", format: "TradDraft",    expansion: "SOS", wins: 3, losses: 0, isTrophy: true,  colors: "UR",   startedAt: "2026-04-26T03:01:30Z", finishedAt: "2026-04-26T13:27:01Z" },
  { slug: "chonce", setCode: "SOS", eventId: "d15969c4-bc52-4926-b4db-1e57d8fe60b5", format: "TradDraft",    expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WB",   startedAt: "2026-04-26T02:02:12Z", finishedAt: "2026-04-26T02:58:42Z" },
  { slug: "chonce", setCode: "SOS", eventId: "9b26cf8e-2417-4d09-946b-cd7a1b6b8193", format: "TradDraft",    expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WR",   startedAt: "2026-04-26T00:27:38Z", finishedAt: "2026-04-26T02:00:20Z" },
  { slug: "chonce", setCode: "SOS", eventId: "4deebe7f-a0e6-42e8-8fd1-876bcd2676dc", format: "TradDraft",    expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WR",   startedAt: "2026-04-25T22:42:17Z", finishedAt: "2026-04-26T00:24:13Z" },
];
