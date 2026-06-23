import { useState } from "react";
import { p0p1DevEnabled, useP0P1DevPreset, setP0P1DevPreset, P0P1_DEV_PRESETS } from "../../data/p0p1DevState";

export function P0P1DevPanel() {
  if (!p0p1DevEnabled) return null;
  return <DevPanelBody />;
}

function DevPanelBody() {
  const preset = useP0P1DevPreset();
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-3 right-3 z-[100] flex flex-col items-end gap-2 font-display">
      {open && (
        <div className="flex flex-col gap-1 rounded-md border border-green bg-black p-2 shadow-lg">
          <div className="px-1 pb-1 text-[10px] tracking-[0.16em] text-green">DEV · P0P1 STATE</div>
          {P0P1_DEV_PRESETS.map((option) => {
            const active = option.value === preset;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setP0P1DevPreset(option.value)}
                className={`rounded px-3 py-2 text-left text-[13px] tracking-wide transition-colors ${
                  active ? "bg-green text-black" : "text-green hover:bg-green/20"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="rounded-full border border-green bg-black px-3 py-2 text-[12px] tracking-wide text-green shadow-lg"
      >
        DEV {preset === "live" ? "" : `· ${labelFor(preset)}`}
      </button>
    </div>
  );
}

function labelFor(value: string): string {
  return P0P1_DEV_PRESETS.find((option) => option.value === value)?.label ?? value;
}
