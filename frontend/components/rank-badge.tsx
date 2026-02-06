"use client";

import { Medal, Star, Trophy, Flame, Crown, Zap } from "lucide-react";
import type { RankTierId } from "@/lib/api";

type RankBadgeProps = {
  tierId: RankTierId;
  tierName?: string | null;
  size?: "sm" | "md";
};

const TIER_LABELS: Record<RankTierId, string> = {
  bronze: "Bronze Trailblazer",
  silver: "Silver Strider",
  gold: "Gold Pacemaker",
  platinum: "Platinum Marathoner",
  diamond: "Diamond Elite",
  world_class: "World Class Legend",
};

function iconForTier(tier: RankTierId, size: number) {
  switch (tier) {
    case "bronze":
      return <Medal className={`text-amber-700`} width={size} height={size} />;
    case "silver":
      return <Medal className={`text-slate-400`} width={size} height={size} />;
    case "gold":
      return <Trophy className={`text-yellow-500`} width={size} height={size} />;
    case "platinum":
      return <Star className={`text-sky-400`} width={size} height={size} />;
    case "diamond":
      return <Zap className={`text-cyan-300`} width={size} height={size} />;
    case "world_class":
      return <Crown className={`text-purple-400`} width={size} height={size} />;
    default:
      return <Medal width={size} height={size} />;
  }
}

export function RankBadge({ tierId, tierName, size = "md" }: RankBadgeProps) {
  const label = tierName || TIER_LABELS[tierId] || tierId;
  const isSm = size === "sm";
  const iconSize = isSm ? 14 : 16;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground`}
    >
      {iconForTier(tierId, iconSize)}
      <span className={isSm ? "" : "px-0.5"}>{label}</span>
    </span>
  );
}

