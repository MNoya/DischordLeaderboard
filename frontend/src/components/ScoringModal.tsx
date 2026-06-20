import { useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { ScoringExplainer } from "./ScoringExplainer";

// The scoring explanation is a deep-linkable modal: it opens whenever the URL
// hash is #points and closes by stripping the hash, so it survives reloads and
// is shareable. Mounted once at the app root; any ScoringInfoButton just adds
// the hash.
export const SCORING_HASH = "#about";

export function ScoringModalHost() {
  const location = useLocation();
  const navigate = useNavigate();
  const open = location.hash === SCORING_HASH;

  const close = useCallback(() => {
    navigate({ pathname: location.pathname, search: location.search }, { replace: true });
  }, [navigate, location.pathname, location.search]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close();
      }
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, close]);

  if (!open) {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start md:items-center justify-center p-3 md:p-6 overflow-y-auto animate-fadeIn">
      <div className="absolute inset-0 bg-black/70" onClick={close} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Leaderboard points"
        className="relative z-10 w-full max-w-[1040px] my-auto bg-bg border border-border2 themed-scrollbar max-h-[92vh] overflow-y-auto p-5 md:p-8"
      >
        <button
          type="button"
          onClick={close}
          aria-label="Close"
          className="absolute top-3 right-3 text-muted hover:text-text transition-colors p-1 bg-transparent border-0 cursor-pointer"
        >
          <X size={18} />
        </button>
        <ScoringExplainer />
      </div>
    </div>,
    document.body,
  );
}
