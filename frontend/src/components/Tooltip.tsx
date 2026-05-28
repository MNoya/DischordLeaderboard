import React from "react";
import { Root, Trigger, Portal, Content, Arrow } from "@radix-ui/react-tooltip";
import { cn } from "../lib/utils";

export function Tooltip({
  label,
  side,
  align,
  children,
  className,
}: {
  label: string;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Root>
      <Trigger asChild>{children}</Trigger>
      <Portal>
        <Content
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            "z-50 pointer-events-none select-none rounded-md px-2.5 py-1.5",
            "bg-zinc-900 text-zinc-100 text-[12px] leading-tight",
            "shadow-md shadow-black/40",
            className,
          )}
        >
          {label}
          <Arrow className="fill-zinc-900" width={10} height={5} />
        </Content>
      </Portal>
    </Root>
  );
}
