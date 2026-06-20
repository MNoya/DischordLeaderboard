import { useEffect, useState, type ReactNode } from "react";

export const CROSSFADE_MS = 220;

type Layer = { key: string; content: ReactNode };

export function Crossfade({ transitionKey, children }: { transitionKey: string; children: ReactNode }) {
  const [current, setCurrent] = useState<Layer>({ key: transitionKey, content: children });
  const [outgoing, setOutgoing] = useState<Layer | null>(null);

  useEffect(() => {
    if (transitionKey === current.key) {
      setCurrent({ key: transitionKey, content: children });
      return;
    }
    setOutgoing(current);
    setCurrent({ key: transitionKey, content: children });
    const timer = setTimeout(() => setOutgoing(null), CROSSFADE_MS);
    return () => clearTimeout(timer);
  }, [transitionKey, children, current.key]);

  return (
    <div className="relative">
      <div key={current.key} className="animate-fadeIn">
        {current.content}
      </div>
      {outgoing ? (
        <div key={outgoing.key} className="animate-fadeOut absolute inset-x-0 top-0 pointer-events-none">
          {outgoing.content}
        </div>
      ) : null}
    </div>
  );
}
