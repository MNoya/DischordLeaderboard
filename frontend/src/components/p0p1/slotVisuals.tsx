import { Pip } from "../ManaPips";
import { keyruneClass } from "../Brand";
import { P0P1_SET_CODE } from "../../data/p0p1Slots";
import type { SlotKey } from "../../types/p0p1";

type Color = "W" | "U" | "B" | "R" | "G";

const UNCOMMON_SILVER_GRADIENT =
  "repeating-linear-gradient(135deg, #8a94a3 0px, #c9cfd8 2px, #e6e9ef 4px, #c9cfd8 6px, #8a94a3 8px)";
const UNCOMMON_GLYPH_GRADIENT = "linear-gradient(to bottom, #d6dbe3 0%, #ffffff 48%, #ffffff 56%, #cdd3dc 100%)";

export const SLOT_ACCENT: Record<SlotKey, string> = {
  white_common: "#e8e4cf",
  blue_common: "#5aa9e6",
  black_common: "#9b86c4",
  red_common: "#e0625c",
  green_common: "#54b87a",
  multicolor_uncommon: "#ffc63a",
  wildcard_common: "#ffffff",
  wildcard_uncommon: UNCOMMON_SILVER_GRADIENT,
};

const MONO: Partial<Record<SlotKey, Color>> = {
  white_common: "W",
  blue_common: "U",
  black_common: "B",
  red_common: "R",
  green_common: "G",
};

export function SlotPip({ slotKey, size = 15 }: { slotKey: SlotKey; size?: number }) {
  const mono = MONO[slotKey];
  if (mono) {
    return <Pip c={mono} size={Math.round(size * 0.64)} />;
  }
  if (slotKey === "multicolor_uncommon") {
    return <i className="ms ms-multicolor ms-duo ms-duo-color ms-grad" style={{ fontSize: size, lineHeight: 1 }} />;
  }
  const setSymbol = `ss ss-${keyruneClass(P0P1_SET_CODE)}`;
  if (slotKey === "wildcard_common") {
    return <i className={setSymbol} style={{ fontSize: size, color: "#fff", lineHeight: 1 }} />;
  }
  return (
    <i
      className={`${setSymbol} ss-uncommon ss-grad`}
      style={{
        fontSize: size,
        lineHeight: 1,
        background: UNCOMMON_GLYPH_GRADIENT,
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        WebkitTextFillColor: "transparent",
      }}
    />
  );
}
