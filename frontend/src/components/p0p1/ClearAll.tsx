import { useEffect, useState } from "react";

interface Props {
  onClear: () => void;
  clearing: boolean;
  visible?: boolean;
  className?: string;
}

export function ClearAll({ onClear, clearing, visible = true, className = "flex justify-center mt-1.5" }: Props) {
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    if (!confirming) return;
    const id = setTimeout(() => setConfirming(false), 3000);
    return () => clearTimeout(id);
  }, [confirming]);
  const handleClear = () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    onClear();
  };
  const shown = visible && !clearing;
  return (
    <div className={`${className} ${shown ? "" : "invisible"}`}>
      <button
        type="button"
        onClick={handleClear}
        disabled={!shown}
        className={`bg-transparent border-0 text-[12px] cursor-pointer transition-colors ${
          confirming ? "text-red font-semibold" : "text-dim hover:text-red"
        }`}
      >
        {confirming ? "Clear all picks?" : "CLEAR ALL PICKS"}
      </button>
    </div>
  );
}
