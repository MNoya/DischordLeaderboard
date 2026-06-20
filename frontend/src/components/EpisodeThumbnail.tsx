import { useEffect, useRef, useState } from "react";
import { LLU_LOGO_SRC } from "./Brand";
import { cn } from "../lib/utils";

export function EpisodeThumbnail({
  src,
  pending,
  className,
  portrait,
}: {
  src?: string;
  pending?: boolean;
  className?: string;
  portrait?: boolean;
}) {
  const [loaded, setLoaded] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [failed, setFailed] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const img = imgRef.current;
    const alreadyComplete = img?.complete && img.naturalWidth > 0;
    setLoaded(!!alreadyComplete);
    setRevealed(false);
    setFailed(false);
  }, [src]);

  useEffect(() => {
    if (!loaded) {
      return;
    }
    const timer = setTimeout(() => setRevealed(true), 350);
    return () => clearTimeout(timer);
  }, [loaded]);

  const ready = !!src && !failed;
  const showBranded = (!src && !pending) || failed;
  const showSkeleton = !showBranded && !revealed;
  const skeletonLogoClass = portrait ? "w-[70%] max-w-[220px]" : "w-[42%] max-w-[220px]";
  const brandedLogoClass = portrait ? "w-1/2 max-w-[180px]" : "w-[34%] max-w-[180px]";

  return (
    <>
      {showSkeleton ? (
        <div className="absolute inset-0 flex items-center justify-center overflow-hidden bg-surface">
          <img src={LLU_LOGO_SRC} alt="" className={cn(skeletonLogoClass, "opacity-[0.06] grayscale-[0.6]")} />
          <div className="pointer-events-none absolute inset-0 animate-[thumbSweep_1.8s_ease-in-out_-0.64s_infinite] bg-[linear-gradient(100deg,transparent_25%,rgba(255,255,255,0.13)_50%,transparent_75%)]" />
        </div>
      ) : null}
      {showBranded ? (
        <div className="absolute inset-0 flex items-center justify-center bg-surface">
          <img src={LLU_LOGO_SRC} alt="" className={cn(brandedLogoClass, "opacity-90", className)} />
        </div>
      ) : null}
      {ready ? (
        <img
          ref={imgRef}
          src={src}
          alt=""
          loading="lazy"
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
          className={cn(
            "absolute inset-0 h-full w-full object-cover transition-opacity duration-500",
            loaded ? "opacity-100" : "opacity-0",
            className,
          )}
        />
      ) : null}
    </>
  );
}
