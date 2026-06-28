export interface Card {
  name: string;
  manaCost: string;
  cmc: number;
  colors: string[];
  rarity: "common" | "uncommon" | "rare";
  typeLine: string;
  collectorNumber: string;
  imageSmall: string;
  imageNormal: string;
  imageArtCrop: string;
}

export interface P0P1Pick {
  slot: SlotKey;
  cardName: string;
  lastUpdated: string;
}

export type SlotKey =
  | "white_common"
  | "blue_common"
  | "black_common"
  | "red_common"
  | "green_common"
  | "multicolor_uncommon"
  | "wildcard_common"
  | "wildcard_uncommon";

export interface SlotDefinition {
  key: SlotKey;
  label: string;
  filter: (card: Card, pickedCards: Set<string>) => boolean;
}

export interface P0P1PickStat {
  setCode: string;
  slot: SlotKey;
  cardName: string;
  pickCount: number;
  pickPct: number;
}

export interface P0P1BallotRow {
  setCode: string;
  ballotId: number;
  name: string;
  avatarUrl: string | null;
  slot: SlotKey;
  cardName: string;
}

export type PickVersusState = "matched" | "minority" | "rogue";

export interface PickVersusSide {
  name: string;
  imageUrl: string;
  pickPct: number;
}

export interface PickVersus {
  slotKey: SlotKey;
  slotLabel: string;
  state: PickVersusState;
  agreed: boolean;
  tiedCount: number;
  crowd: PickVersusSide;
  yours: PickVersusSide;
}
