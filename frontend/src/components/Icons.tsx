import React from "react";
import {
  ArrowRight as LR_ArrowRight,
  ArrowUp as LR_ArrowUp,
  ChevronLeft as LR_ChevronLeft,
  ChevronRight as LR_ChevronRight,
  Clock as LR_Clock,
  ExternalLink as LR_ExternalLink,
  Globe as LR_Globe,
  Image as LR_Image,
  Info as LR_Info,
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

function withShrink<P extends { className?: string }>(
  Icon: React.ComponentType<P>,
): React.ComponentType<P> {
  return function ShrunkIcon(props: P) {
    const className = props.className ? `shrink-0 ${props.className}` : "shrink-0";
    return <Icon {...props} className={className} />;
  };
}

const _ArrowRight = withShrink(LR_ArrowRight);
export function ArrowRight(
  props: React.ComponentProps<typeof LR_ArrowRight>,
) {
  return <_ArrowRight strokeWidth={3} {...props} />;
}
export const ArrowUp = withShrink(LR_ArrowUp);
export const ChevronLeft = withShrink(LR_ChevronLeft);
export const ChevronRight = withShrink(LR_ChevronRight);
export const Clock = withShrink(LR_Clock);
export const ExternalLink = withShrink(LR_ExternalLink);
export const Globe = withShrink(LR_Globe);
export const ImageIcon = withShrink(LR_Image);
export const Info = withShrink(LR_Info);
export const TbCards = withShrink(R_TbCards);
export const LuScrollText = withShrink(R_LuScrollText);
export const GiRoundTable = withShrink(R_GiRoundTable);
export const BsAsterisk = withShrink(R_BsAsterisk);
export const BsPaletteFill = withShrink(R_BsPaletteFill);
export const SiDiscord = withShrink(R_SiDiscord);
export const SiGithub = withShrink(R_SiGithub);
export const SiPatreon = withShrink(R_SiPatreon);
export const SiYoutube = withShrink(R_SiYoutube);
