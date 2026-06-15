import type { Card, SlotDefinition } from "../types/p0p1";

// TODO: get this data from the database instead of hardcoding to support other sets
export const P0P1_SET_CODE = "MSH";
export const P0P1_SET_NAME = "Marvel Super Heroes";
export const P0P1_VOTING_DEADLINE = new Date("2026-06-23T15:00:00Z");

function isBasicLand(card: Card) {
  return card.typeLine.startsWith("Basic Land");
}

function monoColor(color: string) {
  return (card: Card, picked: Set<string>) =>
    card.rarity === "common" &&
    card.colors.length === 1 &&
    card.colors[0] === color &&
    !picked.has(card.name);
}

export const SLOTS: SlotDefinition[] = [
  { key: "white_common", label: "White Common", filter: monoColor("W") },
  { key: "blue_common", label: "Blue Common", filter: monoColor("U") },
  { key: "black_common", label: "Black Common", filter: monoColor("B") },
  { key: "red_common", label: "Red Common", filter: monoColor("R") },
  { key: "green_common", label: "Green Common", filter: monoColor("G") },
  {
    key: "multicolor_uncommon",
    label: "Multicolor Uncommon",
    filter: (card, picked) =>
      card.rarity === "uncommon" &&
      card.colors.length >= 2 &&
      !picked.has(card.name),
  },
  {
    key: "wildcard_common",
    label: "Wildcard Common",
    filter: (card, picked) =>
      card.rarity === "common" && !isBasicLand(card) && !picked.has(card.name),
  },
  {
    key: "wildcard_uncommon",
    label: "Wildcard Uncommon",
    filter: (card, picked) =>
      card.rarity === "uncommon" && !picked.has(card.name),
  },
];
