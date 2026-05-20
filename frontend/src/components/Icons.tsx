import React from "react";
import {
  ArrowRight as LR_ArrowRight,
  ArrowUp as LR_ArrowUp,
  ChevronLeft as LR_ChevronLeft,
  ChevronRight as LR_ChevronRight,
  Clock as LR_Clock,
  ExternalLink as LR_ExternalLink,
  Globe as LR_Globe,
} from "lucide-react";
import { TbCards as R_TbCards } from "react-icons/tb";
import { LuScrollText as R_LuScrollText } from "react-icons/lu";
import { GiRoundTable as R_GiRoundTable } from "react-icons/gi";
import {
  BsAsterisk as R_BsAsterisk,
  BsPaletteFill as R_BsPaletteFill,
} from "react-icons/bs";
import {
  SiDiscord as R_SiDiscord,
  SiGithub as R_SiGithub,
  SiPatreon as R_SiPatreon,
  SiYoutube as R_SiYoutube,
} from "react-icons/si";

// Bebas Neue caps sit ~1px above their line-box center while SVG icons render
// at the geometric center; sharing a row makes icons look low. Every icon used
// in the app is re-exported from here with `.icon-cap-align` baked in so callers
// never have to think about it. Need a new icon? Wrap it here and import from
// Icons instead of from lucide-react / react-icons directly.

function withCapAlign<P extends { className?: string }>(
  Icon: React.ComponentType<P>,
): React.ComponentType<P> {
  return function CapAlignedIcon(props: P) {
    const className = props.className
      ? `icon-cap-align shrink-0 ${props.className}`
      : "icon-cap-align shrink-0";
    return <Icon {...props} className={className} />;
  };
}

const _ArrowRight = withCapAlign(LR_ArrowRight);
export function ArrowRight(
  props: React.ComponentProps<typeof LR_ArrowRight>,
) {
  return <_ArrowRight strokeWidth={3} {...props} />;
}
export const ArrowUp = withCapAlign(LR_ArrowUp);
export const ChevronLeft = withCapAlign(LR_ChevronLeft);
export const ChevronRight = withCapAlign(LR_ChevronRight);
export const Clock = withCapAlign(LR_Clock);
export const ExternalLink = withCapAlign(LR_ExternalLink);
export const Globe = withCapAlign(LR_Globe);
export const TbCards = withCapAlign(R_TbCards);
export const LuScrollText = withCapAlign(R_LuScrollText);
export const GiRoundTable = withCapAlign(R_GiRoundTable);
export const BsAsterisk = withCapAlign(R_BsAsterisk);
export const BsPaletteFill = withCapAlign(R_BsPaletteFill);
export const SiDiscord = withCapAlign(R_SiDiscord);
export const SiGithub = withCapAlign(R_SiGithub);
export const SiPatreon = withCapAlign(R_SiPatreon);
export const SiYoutube = withCapAlign(R_SiYoutube);
