import { useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import {  ZoomInIcon } from "lucide-react";
import { useIsMobile } from "../../lib/use-is-mobile";

const PREVIEW_W = 232;
const PREVIEW_RATIO = 1.4;
const PREVIEW_GAP = 12;

interface Props {
  imageUrl: string;
  alt: string;
  children: ReactNode;
}

interface PreviewAnchor {
  left: number;
  below: boolean;
  arrowLeft: number;
  edge: number;
}

export function CardImagePreview({ imageUrl, alt, children }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mobile = useIsMobile();
  const [anchor, setAnchor] = useState<PreviewAnchor | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const openPreview = () => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const previewH = PREVIEW_W * PREVIEW_RATIO;
    const below = window.innerHeight - rect.bottom >= previewH + PREVIEW_GAP + 8;
    const centerX = rect.left + rect.width / 2;
    const left = Math.min(Math.max(centerX - PREVIEW_W / 2, 8), window.innerWidth - PREVIEW_W - 8);
    const edge = below ? rect.bottom + PREVIEW_GAP : window.innerHeight - rect.top + PREVIEW_GAP;
    const arrowLeft = Math.min(Math.max(centerX - left, 14), PREVIEW_W - 14);
    setAnchor({ left, below, arrowLeft, edge });
  };

  return (
    <>
      <div
        ref={ref}
        className="relative shrink-0 cursor-zoom-in"
        onMouseEnter={mobile ? undefined : openPreview}
        onMouseLeave={mobile ? undefined : () => setAnchor(null)}
        onClick={mobile ? (e) => { e.stopPropagation(); setModalOpen(true); } : undefined}
      >
        {children}
        <div className="absolute bottom-0 right-0 bg-black/60 p-0.5 flex items-center justify-center">
          <ZoomInIcon size={16} className="text-white" />
        </div>
      </div>
      {anchor && createPortal(
        <div
          className="pointer-events-none fixed z-[100]"
          style={{
            left: anchor.left,
            width: PREVIEW_W,
            ...(anchor.below ? { top: anchor.edge } : { bottom: anchor.edge }),
          }}
        >
          <svg
            width="22"
            height={PREVIEW_GAP}
            viewBox={`0 0 22 ${PREVIEW_GAP}`}
            className="absolute"
            style={anchor.below
              ? { top: -(PREVIEW_GAP - 1), left: anchor.arrowLeft - 11 }
              : { bottom: -(PREVIEW_GAP - 1), left: anchor.arrowLeft - 11 }
            }
          >
            <path
              d={anchor.below
                ? `M0 ${PREVIEW_GAP} L11 0 L22 ${PREVIEW_GAP} Z`
                : `M0 0 L11 ${PREVIEW_GAP} L22 0 Z`
              }
              fill="#3b4458"
            />
          </svg>
          <div className="overflow-hidden rounded-lg border border-border2 bg-surface shadow-2xl">
            <img src={imageUrl} alt={alt} className="w-full" />
          </div>
        </div>,
        document.body,
      )}
      {modalOpen && createPortal(
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-6"
          onClick={(e) => { e.stopPropagation(); setModalOpen(false); }}
        >
          <div
            className="w-full max-w-[320px] overflow-hidden rounded-xl border border-border2 bg-surface shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <img src={imageUrl} alt={alt} className="w-full" />
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
