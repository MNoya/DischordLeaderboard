import type {
  PlayerDraftEvent,
  PlayerFormatBreakdown,
} from "../../types/leaderboard";

// Real production data for nlaframboise on SOS, snapshot 2026-05-09.
// Format breakdown aggregated from player_stats; scoreContribution split
// proportionally by trophies until the backend exposes per-format scores.
// Draft events are the most recent 30 from draft_events.

export const nlaframboiseFormatBreakdown: PlayerFormatBreakdown[] = [
  { setCode: "SOS", slug: "nlaframboise", formatLabel: "Trad", events: 94, wins: 199, losses: 77, trophies: 37, scoreContribution: 121.51 },
];

export const nlaframboiseDraftEvents: PlayerDraftEvent[] = [
  { slug: "nlaframboise", setCode: "SOS", eventId: "800205e6-980e-46ea-9b69-8b9a8278763f", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "BG", startedAt: "2026-05-08T20:41:30Z", finishedAt: "2026-05-08T22:26:08Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "939a9cf2-e2af-4942-afcb-5f2be819c50a", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "UR", startedAt: "2026-05-08T19:32:29Z", finishedAt: "2026-05-08T20:34:53Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "d2db4e50-81b7-464f-9150-ab8ff49ebff5", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-08T17:59:42Z", finishedAt: "2026-05-08T18:56:21Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "c1a42eba-7ed2-4263-84d2-d44cb58e6127", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-08T16:18:11Z", finishedAt: "2026-05-08T17:27:36Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "8ca6324d-3a44-4e7d-a36c-c1f48ecca998", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WR", startedAt: "2026-05-08T15:18:06Z", finishedAt: "2026-05-08T16:17:29Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "9f7ef957-e6fd-4f76-b136-ee1af4350408", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-08T14:11:34Z", finishedAt: "2026-05-08T15:03:39Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "b69511a3-4b10-489a-8250-10785f995f10", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WR", startedAt: "2026-05-07T19:38:04Z", finishedAt: "2026-05-08T14:08:21Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "cc33e982-3566-411e-bbad-13637a929517", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WR", startedAt: "2026-05-07T18:24:49Z", finishedAt: "2026-05-07T19:30:12Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "e9e5a530-7a5d-413c-8592-45eed05c26af", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WB", startedAt: "2026-05-07T16:05:44Z", finishedAt: "2026-05-07T18:22:41Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "a0165ba9-d908-4599-ab36-e700b2712786", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WRu", startedAt: "2026-05-07T15:06:19Z", finishedAt: "2026-05-07T16:04:32Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "4f01b965-0d61-4167-8078-80f96fa1fe84", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "URw", startedAt: "2026-05-06T20:49:49Z", finishedAt: "2026-05-07T15:04:33Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "8d8c589c-80ab-455f-96cb-b263a252edb3", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "BG", startedAt: "2026-05-06T20:13:01Z", finishedAt: "2026-05-06T20:48:02Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "4e52de45-a242-4c2d-a0aa-8658440ed20d", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WR", startedAt: "2026-05-06T18:27:50Z", finishedAt: "2026-05-06T20:07:54Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "c790e6d9-f653-4758-9bb1-d37873779266", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UGbr", startedAt: "2026-05-06T16:48:19Z", finishedAt: "2026-05-06T18:24:18Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "b21e1f38-906a-4c19-b2f0-8938fdc53398", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WRu", startedAt: "2026-05-06T15:25:13Z", finishedAt: "2026-05-06T16:31:29Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "58a410bd-8571-4c9c-8d77-d5d7bcb9301c", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "URwb", startedAt: "2026-05-06T14:12:47Z", finishedAt: "2026-05-06T15:21:01Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "39fa69b3-804a-4f9e-800d-942a11737a58", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "WB", startedAt: "2026-05-05T21:00:15Z", finishedAt: "2026-05-06T14:06:32Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "94adc5cf-e5c7-4d83-a030-86fc92a53030", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WR", startedAt: "2026-05-05T19:44:43Z", finishedAt: "2026-05-05T20:55:07Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "100b56f8-9fd4-4e05-a1b1-f4982903d33f", format: "TradDraft", expansion: "SOS", wins: 0, losses: 2, isTrophy: false, colors: "BGw", startedAt: "2026-05-05T18:51:50Z", finishedAt: "2026-05-05T19:41:05Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "fcdf9233-4ef7-443b-b1c9-0a97898cb2d8", format: "TradDraft", expansion: "SOS", wins: 1, losses: 2, isTrophy: false, colors: "URw", startedAt: "2026-05-05T17:25:25Z", finishedAt: "2026-05-05T18:49:21Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "dcfc236d-30e8-46bb-b6b9-b26d9b0d3fa5", format: "TradDraft", expansion: "SOS", wins: 0, losses: 2, isTrophy: false, colors: "URGwb", startedAt: "2026-05-05T16:03:46Z", finishedAt: "2026-05-05T17:22:14Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "0e4b0249-eed7-47ff-94f2-be465053692f", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WRu", startedAt: "2026-05-05T14:34:47Z", finishedAt: "2026-05-05T15:57:59Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "3176f482-60d8-4dfc-a892-fc7237813a3b", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WRb", startedAt: "2026-05-04T23:43:49Z", finishedAt: "2026-05-05T14:31:41Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "6acaac29-e798-4f72-9182-7259ac8543a1", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "UGb", startedAt: "2026-05-04T21:48:28Z", finishedAt: "2026-05-04T22:51:56Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "bd2a0fd5-8362-45ac-bc18-9395c7bdb63d", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "UR", startedAt: "2026-05-03T19:27:43Z", finishedAt: "2026-05-04T21:47:24Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "bfbd77ee-1221-456f-abfd-e6837b041a8e", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "WB", startedAt: "2026-05-03T18:38:53Z", finishedAt: "2026-05-03T19:26:09Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "ccfe0bf6-b266-496e-97c4-669fdea03f6e", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WB", startedAt: "2026-05-03T15:13:21Z", finishedAt: "2026-05-03T16:42:10Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "ac69914c-57dd-423d-9021-3192bc7985f9", format: "TradDraft", expansion: "SOS", wins: 0, losses: 2, isTrophy: false, colors: "UR", startedAt: "2026-05-03T14:12:16Z", finishedAt: "2026-05-03T14:57:16Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "4f3fc687-247b-4ca8-987e-4733778ba384", format: "TradDraft", expansion: "SOS", wins: 3, losses: 0, isTrophy: true, colors: "URGb", startedAt: "2026-05-03T00:36:38Z", finishedAt: "2026-05-03T01:29:53Z" },
  { slug: "nlaframboise", setCode: "SOS", eventId: "d3991f90-fdcb-4a95-821a-4de2c1a6e977", format: "TradDraft", expansion: "SOS", wins: 2, losses: 1, isTrophy: false, colors: "WRb", startedAt: "2026-05-02T23:28:45Z", finishedAt: "2026-05-03T00:35:52Z" },
];
