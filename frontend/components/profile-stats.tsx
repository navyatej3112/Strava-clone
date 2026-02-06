"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  athletesApi,
  ranksApi,
  type AthleteSummary,
  type AthleteWeek,
  type RankMeResponse,
  type RankHistoryResponse,
} from "@/lib/api";
import { formatDistance, formatDuration } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LineChart,
  Line,
} from "recharts";
import { RankBadge } from "@/components/rank-badge";
import { RankProgress } from "@/components/rank-progress";
import { Button } from "@/components/ui/button";
import { useToast } from "@/lib/toast-context";
import { useAuth } from "@/lib/auth-context";

type RangeKey = "7d" | "30d" | "ytd";

const RANGE_LABELS: { key: RangeKey; label: string }[] = [
  { key: "7d", label: "7d" },
  { key: "30d", label: "30d" },
  { key: "ytd", label: "YTD" },
];

interface ProfileStatsProps {
  /** undefined = current user (me) */
  userId: string | undefined;
}

export function ProfileStats({ userId }: ProfileStatsProps) {
  const [range, setRange] = useState<RangeKey>("30d");
  const [summary, setSummary] = useState<AthleteSummary | null>(null);
  const [weeks, setWeeks] = useState<AthleteWeek[]>([]);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [weeksLoading, setWeeksLoading] = useState(true);
  const [summaryError, setSummaryError] = useState(false);
  const [weeksError, setWeeksError] = useState(false);
  const [rank, setRank] = useState<RankMeResponse | null>(null);
  const [rankLoading, setRankLoading] = useState(true);
  const [rankError, setRankError] = useState(false);
  const [history, setHistory] = useState<RankHistoryResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState(false);
  const { toast } = useToast();
  const { user: me } = useAuth();

  useEffect(() => {
    setSummaryLoading(true);
    setSummaryError(false);
    athletesApi
      .getSummary(userId ?? undefined, range)
      .then(setSummary)
      .catch(() => {
        setSummaryError(true);
        setSummary(null);
      })
      .finally(() => setSummaryLoading(false));
  }, [userId, range]);

  useEffect(() => {
    setWeeksLoading(true);
    setWeeksError(false);
    athletesApi
      .getWeeks(userId ?? undefined, 12)
      .then(setWeeks)
      .catch(() => {
        setWeeksError(true);
        setWeeks([]);
      })
      .finally(() => setWeeksLoading(false));
  }, [userId]);

  // PaceRank: for me or other users
  useEffect(() => {
    setRankLoading(true);
    setRankError(false);
    if (userId === undefined) {
      ranksApi
        .getMe()
        .then(setRank)
        .catch(() => {
          setRankError(true);
          setRank(null);
        })
        .finally(() => setRankLoading(false));
    } else {
      ranksApi
        .getUser(userId)
        .then(setRank)
        .catch(() => {
          setRankError(true);
          setRank(null);
        })
        .finally(() => setRankLoading(false));
    }
  }, [userId]);

  // Rank history
  useEffect(() => {
    setHistoryLoading(true);
    setHistoryError(false);
    if (userId === undefined) {
      ranksApi
        .getHistoryMe(30)
        .then(setHistory)
        .catch(() => {
          setHistoryError(true);
          setHistory(null);
        })
        .finally(() => setHistoryLoading(false));
    } else {
      ranksApi
        .getHistoryUser(userId, 30)
        .then(setHistory)
        .catch(() => {
          setHistoryError(true);
          setHistory(null);
        })
        .finally(() => setHistoryLoading(false));
    }
  }, [userId]);

  async function handleRecompute() {
    if (!me || userId !== undefined) return;
    const oldTier = rank?.rank_tier;
    try {
      const response = await ranksApi.recomputeMe();
      
      // If synchronous (no Redis), result is already available
      if (response.status === "finished" && response.result) {
        const newRank = response.result as RankMeResponse;
        setRank(newRank);
        ranksApi.getHistoryMe(30).then(setHistory).catch(() => {});
        if (oldTier && newRank.rank_tier && newRank.rank_tier_name) {
          const tierOrder: Record<string, number> = {
            bronze: 0,
            silver: 1,
            gold: 2,
            platinum: 3,
            diamond: 4,
            world_class: 5,
          };
          if (tierOrder[newRank.rank_tier] > (tierOrder[oldTier] ?? -1)) {
            toast(`Rank Up! You reached ${newRank.rank_tier_name}`, "success");
          }
        }
        return;
      }
      
      // Async job: poll for status
      if (response.status === "queued" && response.job_id) {
        const jobId = response.job_id;
        let attempts = 0;
        const maxAttempts = 30; // 30 seconds max
        
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const status = await ranksApi.getRecomputeStatus(jobId);
            if (status.status === "finished" && status.result) {
              clearInterval(pollInterval);
              const newRank = status.result as RankMeResponse;
              setRank(newRank);
              ranksApi.getHistoryMe(30).then(setHistory).catch(() => {});
              if (oldTier && newRank.rank_tier && newRank.rank_tier_name) {
                const tierOrder: Record<string, number> = {
                  bronze: 0,
                  silver: 1,
                  gold: 2,
                  platinum: 3,
                  diamond: 4,
                  world_class: 5,
                };
                if (tierOrder[newRank.rank_tier] > (tierOrder[oldTier] ?? -1)) {
                  toast(`Rank Up! You reached ${newRank.rank_tier_name}`, "success");
                }
              }
            } else if (status.status === "failed") {
              clearInterval(pollInterval);
              toast(`Rank recompute failed: ${status.error || "Unknown error"}`, "error");
            } else if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
              toast("Rank recompute timed out", "error");
            }
          } catch {
            if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
              toast("Rank recompute timed out", "error");
            }
          }
        }, 1000);
      }
    } catch {
      toast("Failed to recompute rank", "error");
    }
  }

  const hasSummary = summary && summary.totals.activities > 0;
  const hasWeeks = weeks.length > 0 && weeks.some((w) => w.distance_m > 0);

  return (
    <Card>
      <CardHeader className="pb-2 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Stats</h2>
        </div>
        {/* PaceRank */}
        <div className="space-y-2">
          {rankLoading ? (
            <div className="animate-pulse space-y-2">
              <div className="h-5 w-40 bg-muted rounded" />
              <div className="h-3 w-full bg-muted rounded" />
            </div>
          ) : rankError || !rank || !rank.rank_tier ? (
            <p className="text-xs text-muted-foreground">
              PaceRank will appear here once you log some runs.
            </p>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <RankBadge tierId={rank.rank_tier} tierName={rank.rank_tier_name ?? undefined} size="md" />
                </div>
                <div className="flex items-center gap-2">
                  {typeof rank.rank_score === "number" && (
                    <div className="text-right text-xs text-muted-foreground">
                      <div className="font-semibold text-sm text-foreground">
                        {rank.rank_score.toFixed(1)}
                      </div>
                      <div>PaceRank score (last 30 days)</div>
                    </div>
                  )}
                  {userId === undefined && (
                    <Button variant="outline" size="sm" onClick={handleRecompute}>
                      Recompute
                    </Button>
                  )}
                </div>
              </div>
              <RankProgress
                progress={rank.rank_progress}
                nextTierName={rank.rank_next_tier ? rank.rank_next_tier : null}
              />
              {rank.breakdown && userId === undefined && (
                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                  <span>
                    Runs:{" "}
                    <span className="font-medium text-foreground">
                      {rank.breakdown.runs_count}
                    </span>
                  </span>
                  <span>
                    Distance:{" "}
                    <span className="font-medium text-foreground">
                      {formatDistance(rank.breakdown.total_distance_m)}
                    </span>
                  </span>
                  <span>
                    Avg speed:{" "}
                    <span className="font-medium text-foreground">
                      {rank.breakdown.avg_speed_kmh.toFixed(1)} km/h
                    </span>
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
        {/* Rank history chart */}
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">PaceRank history (last 30 days)</h3>
          {historyLoading ? (
            <div className="h-32 bg-muted rounded animate-pulse" />
          ) : historyError || !history || history.items.length === 0 ? (
            <p className="text-xs text-muted-foreground">No history data yet.</p>
          ) : (
            <div className="h-32 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history.items}>
                  <XAxis
                    dataKey="date"
                    tickFormatter={(v) => {
                      const d = new Date(v);
                      return `${d.getMonth() + 1}/${d.getDate()}`;
                    }}
                    tick={{ fontSize: 10 }}
                  />
                  <YAxis tick={{ fontSize: 10 }} width={40} />
                  <Tooltip
                    formatter={(value: number) => [value.toFixed(1), "Score"]}
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
        <div className="flex gap-1 mt-2">
          {RANGE_LABELS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setRange(key)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                range === key
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {summaryLoading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-16 bg-muted rounded" />
            <div className="h-4 bg-muted rounded w-2/3" />
            <div className="h-4 bg-muted rounded w-1/2" />
          </div>
        ) : summaryError ? (
          <p className="text-sm text-muted-foreground">Unable to load stats.</p>
        ) : !hasSummary ? (
          <p className="text-sm text-muted-foreground">No activities in this range.</p>
        ) : summary ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Activities</p>
                <p className="font-semibold">{summary.totals.activities}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Distance</p>
                <p className="font-semibold">{formatDistance(summary.totals.distance_m)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Time</p>
                <p className="font-semibold">{formatDuration(summary.totals.moving_time_s)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Elevation</p>
                <p className="font-semibold">
                  {summary.totals.elevation_gain_m != null && summary.totals.elevation_gain_m > 0
                    ? `${Math.round(summary.totals.elevation_gain_m)} m`
                    : "—"}
                </p>
              </div>
            </div>
            {summary.by_sport && summary.by_sport.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-2">By sport</h3>
                <ul className="space-y-1.5 text-sm">
                  {summary.by_sport.map((s) => (
                    <li key={s.sport_type} className="flex justify-between">
                      <span className="capitalize">{s.sport_type}</span>
                      <span>
                        {s.activities} · {formatDistance(s.distance_m)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : null}

        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Weekly distance (last 12 weeks)</h3>
          {weeksLoading ? (
            <div className="h-48 bg-muted rounded animate-pulse" />
          ) : weeksError ? (
            <p className="text-sm text-muted-foreground">Unable to load chart.</p>
          ) : !hasWeeks ? (
            <p className="text-sm text-muted-foreground">No data for the chart.</p>
          ) : (
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={weeks}
                  margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                >
                  <XAxis
                    dataKey="week_start"
                    tickFormatter={(v) => {
                      const d = new Date(v);
                      return `${d.getMonth() + 1}/${d.getDate()}`;
                    }}
                    tick={{ fontSize: 11 }}
                  />
                  <YAxis
                    tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v))}
                    tick={{ fontSize: 11 }}
                    width={32}
                  />
                  <Tooltip
                    formatter={(value: number) => [formatDistance(value), "Distance"]}
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  />
                  <Bar dataKey="distance_m" radius={[4, 4, 0, 0]} fill="hsl(var(--primary))">
                    {weeks.map((_, i) => (
                      <Cell key={i} fill="hsl(var(--primary))" />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
