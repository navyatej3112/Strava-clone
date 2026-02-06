"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ranksApi, type RunLeaderboardItem } from "@/lib/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { RankBadge } from "@/components/rank-badge";
import { formatDistance } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

type TabType = "global" | "following";

export default function LeaderboardPage() {
  const [tab, setTab] = useState<TabType>("global");
  const [items, setItems] = useState<RunLeaderboardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [authError, setAuthError] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    setLoading(true);
    setError(false);
    setAuthError(false);
    const fetchFn = tab === "global" ? ranksApi.getRunLeaderboard : ranksApi.getRunLeaderboardFollowing;
    fetchFn(50)
      .then((res) => setItems(res.items))
      .catch((err: Error & { status?: number }) => {
        if (err.status === 401) {
          setAuthError(true);
        } else {
          setError(true);
        }
      })
      .finally(() => setLoading(false));
  }, [tab]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">PaceRank Leaderboard</h1>
      <Card>
        <CardHeader>
          <div className="flex gap-1 mb-2">
            <button
              type="button"
              onClick={() => setTab("global")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === "global"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground"
              }`}
            >
              Global
            </button>
            <button
              type="button"
              onClick={() => setTab("following")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === "following"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground"
              }`}
            >
              Following
            </button>
          </div>
          <p className="text-sm text-muted-foreground">
            {tab === "global"
              ? "Top runners by PaceRank score over the last 30 days (public runs only)."
              : "Runners you follow by PaceRank score over the last 30 days (public runs only)."}
          </p>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          ) : authError ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                <p>Please log in to view the Following leaderboard.</p>
                <Link href="/login" className="text-primary hover:underline mt-2 inline-block">
                  Log in
                </Link>
              </CardContent>
            </Card>
          ) : error ? (
            <p className="text-sm text-muted-foreground">Unable to load leaderboard.</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {tab === "following" ? "No runners you follow on the leaderboard yet." : "No runners on the leaderboard yet."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-xs text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4 text-left">#</th>
                    <th className="py-2 pr-4 text-left">Athlete</th>
                    <th className="py-2 pr-4 text-left">Tier</th>
                    <th className="py-2 pr-4 text-right">Score</th>
                    <th className="py-2 pr-0 text-right">Public runs (30d)</th>
                    <th className="py-2 pl-4 pr-0 text-right">Public distance (30d)</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, idx) => (
                    <tr key={item.user_id} className="border-b last:border-0">
                      <td className="py-2 pr-4 align-middle">{idx + 1}</td>
                      <td className="py-2 pr-4 align-middle">
                        <Link href={`/profile/${item.user_id}`} className="hover:underline font-medium">
                          {item.name}
                        </Link>
                      </td>
                      <td className="py-2 pr-4 align-middle">
                        {item.rank_tier ? (
                          <RankBadge tierId={item.rank_tier} tierName={item.rank_tier_name ?? undefined} size="sm" />
                        ) : (
                          <span className="text-xs text-muted-foreground">Unranked</span>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-right align-middle">
                        {typeof item.rank_score === "number" ? item.rank_score.toFixed(1) : "—"}
                      </td>
                      <td className="py-2 pr-0 text-right align-middle">{item.runs_count_public}</td>
                      <td className="py-2 pl-4 pr-0 text-right align-middle">
                        {formatDistance(item.total_distance_public_m)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

