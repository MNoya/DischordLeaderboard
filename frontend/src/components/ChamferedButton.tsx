import React from "react";

// The green CTA with a top-left / bottom-right chamfer. Used for "VIEW PROFILE"
// callouts on row expanders. Two sizes match the existing visual hierarchy.
//
// `clip-path` has no Tailwind utility so it stays inline.

export function ChamferedButton({
  children,
  onClick,
  size = "md",
  type = "button",
  className,
}: {
  children: React.ReactNode;
  onClick?: (e: React.MouseEvent) => void;
  size?: "sm" | "md";
  type?: "button" | "submit" | "reset";
  className?: string;
}) {
  const isSm = size === "sm";
  const chamfer = isSm ? 6 : 8;
  const base = isSm
    ? "bg-green text-bg font-display tracking-[0.14em] text-[12px] py-[5px] pl-[14px] pr-[16px] cursor-pointer transition-colors hover:bg-green-2"
    : "bg-green text-bg font-display tracking-[0.10em] text-[15px] leading-none pt-[15px] pb-[5px] pl-[22px] pr-[24px] cursor-pointer transition-colors hover:bg-green-2";
  return (
    <button
      type={type}
      onClick={onClick}
      className={className ? `${base} ${className}` : base}
      style={{
        clipPath: `polygon(${chamfer}px 0, 100% 0, calc(100% - ${chamfer}px) 100%, 0 100%)`,
        border: "none",
      }}
    >
      {children}
    </button>
  );
}
