export interface MshCard {
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
  | "wildcard_uncommon"
  | "tiebreaker";

export interface SlotDefinition {
  key: SlotKey;
  label: string;
  filter: (card: MshCard, pickedCards: Set<string>) => boolean;
}
