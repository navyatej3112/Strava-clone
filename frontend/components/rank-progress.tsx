"use client";

import * as React from "react";

type RankProgressProps = {
  progress: number | null | undefined;
  nextTierName?: string | null;
};

export function RankProgress({ progress, nextTierName }: RankProgressProps) {
  const value = Number.isFinite(progress as number) ? Math.max(0, Math.min(1, progress as number)) : 0;
  const pct = Math.round(value * 100);
  const label = nextTierName ? `Next: ${nextTierName}` : "Max tier achieved";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>PaceRank progress</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

