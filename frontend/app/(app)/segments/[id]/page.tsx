"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  segmentsApi,
  type SegmentResponse,
  type SegmentLeaderboardItem,
  type SegmentEffortResponse,
} from "@/lib/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatDistance, formatDuration, formatDate, formatSpeed } from "@/lib/utils";
import { ActivityMap } from "@/components/activity-map";
import { useAuth } from "@/lib/auth-context";

type Tab = "leaderboard" | "mine";

export default function SegmentDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { user } = useAuth();

  const [segment, setSegment] = useState<SegmentResponse | null>(null);
  const [leaderboard, setLeaderboard] = useState<SegmentLeaderboardItem[]>([]);
  const [myEfforts, setMyEfforts] = useState<SegmentEffortResponse[]>([]);
  const [tab, setTab] = useState<Tab>("leaderboard");
  const [loadingSegment, setLoadingSegment] = useState(true);
  const [loadingData, setLoadingData] = useState(true);
  const [errorSegment, setErrorSegment] = useState<"none" | "not_found" | "forbidden" | "other">("none");
  const [errorData, setErrorData] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoadingSegment(true);
    setErrorSegment("none");
    segmentsApi
      .get(id)
      .then(setSegment)
      .catch((err: Error & { status?: number }) => {
        if (err.status === 404) setErrorSegment("not_found");
        else if (err.status === 403) setErrorSegment("forbidden");
        else setErrorSegment("other");
      })
      .finally(() => setLoadingSegment(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    setLoadingData(true);
    setErrorData(false);
    if (tab === "leaderboard") {
      segmentsApi
        .leaderboard(id)
        .then((res) => setLeaderboard(res.items))
        .catch(() => {
          setErrorData(true);
          setLeaderboard([]);
        })
        .finally(() => setLoadingData(false));
    } else if (tab === "mine" && user) {
      segmentsApi
        .myEfforts(id)
        .then(setMyEfforts)
        .catch(() => {
          setErrorData(true);
          setMyEfforts([]);
        })
        .finally(() => setLoadingData(false));
    } else {
      setLoadingData(false);
    }
  }, [id, tab, user]);

  if (loadingSegment) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-1/2 bg-muted rounded animate-pulse" />
        <div className="h-64 bg-muted rounded animate-pulse" />
      </div>
    );
  }

  if (errorSegment === "not_found") {
    return (
      <Card>
        <CardContent className="p-8 text-center text-muted-foreground">Segment not found.</CardContent>
      </Card>
    );
  }

  if (errorSegment === "forbidden") {
    return (
      <Card>
        <CardContent className="p-8 text-center text-muted-foreground">
          <p className="mb-2 font-medium">This segment is private.</p>
          <p className="text-xs">Only the owner can view it.</p>
        </CardContent>
      </Card>
    );
  }

  if (!segment) {
    return null;
  }

  const hasMine = user != null;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{segment.name}</h1>
          {segment.description && (
            <p className="text-sm text-muted-foreground mt-1">{segment.description}</p>
          )}
          <p className="text-sm text-muted-foreground mt-2">
            {formatDistance(segment.distance_m)} · {segment.is_public ? "Public segment" : "Private segment"}
          </p>
        </div>
      </div>

      {segment.polyline && (
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-sm">Map</h2>
          </CardHeader>
          <CardContent>
            <div className="h-64 rounded-md overflow-hidden bg-muted">
              <ActivityMap polyline={segment.polyline} className="h-full w-full" />
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2 mb-2">
            <button
              type="button"
              onClick={() => setTab("leaderboard")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === "leaderboard"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground"
              }`}
            >
              Leaderboard
            </button>
            {hasMine && (
              <button
                type="button"
                onClick={() => setTab("mine")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  tab === "mine"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/80 text-muted-foreground"
                }`}
              >
                My Efforts
              </button>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            Leaderboards include only public activities. Your private runs appear under “My Efforts” but are hidden
            from the public leaderboard.
          </p>
        </CardHeader>
        <CardContent>
          {segmentsApi && leaderboard && leaderboard.length > 0 && (
            <div className="mb-4">
              {segmentsApi && leaderboard && leaderboard.length > 0 && (
                <div className="flex items-center justify-between rounded-md border bg-muted/60 px-3 py-2 text-sm">
                  <div>
                    <span className="font-semibold mr-2">KOM</span>
                    {leaderboard[0].name ? (
                      <span>{leaderboard[0].name}</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">{formatDuration(leaderboard[0].effort_time_s)}</span>
                    <Link href={`/activities/${leaderboard[0].activity_id}`}>
                      <Button size="xs" variant="outline">
                        View activity
                      </Button>
                    </Link>
                  </div>
                </div>
              )}
            </div>
          )}
          {loadingData ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-8 bg-muted rounded animate-pulse" />
              ))}
            </div>
          ) : errorData ? (
            <p className="text-sm text-muted-foreground">Unable to load efforts.</p>
          ) : tab === "leaderboard" ? (
            leaderboard.length === 0 ? (
              <p className="text-sm text-muted-foreground">No efforts on this segment yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b text-xs text-muted-foreground">
                    <tr>
                      <th className="py-2 pr-4 text-left">#</th>
                      <th className="py-2 pr-4 text-left">Athlete</th>
                      <th className="py-2 pr-4 text-right">Time</th>
                      <th className="py-2 pr-4 text-right">Avg speed</th>
                      <th className="py-2 pr-4 text-right">Date</th>
                      <th className="py-2 pr-0 text-right">Activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboard.map((row, idx) => (
                      <tr key={`${row.user_id}-${row.activity_id}-${idx}`} className="border-b last:border-0">
                        <td className="py-2 pr-4 align-middle">{idx + 1}</td>
                        <td className="py-2 pr-4 align-middle">
                          <Link href={`/profile/${row.user_id}`} className="hover:underline">
                            {row.name ?? "Unknown"}
                          </Link>
                        </td>
                        <td className="py-2 pr-4 text-right align-middle">
                          {formatDuration(row.effort_time_s)}
                          {row.is_kom && (
                            <span className="ml-2 inline-flex items-center rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200 px-2 py-0.5 text-[10px] font-semibold">
                              KOM
                            </span>
                          )}
                        </td>
                        <td className="py-2 pr-4 text-right align-middle">
                          {formatSpeed(row.avg_speed_kmh)}
                        </td>
                        <td className="py-2 pr-4 text-right align-middle">
                          {formatDate(row.started_at)}
                        </td>
                        <td className="py-2 pr-0 text-right align-middle">
                          <Link href={`/activities/${row.activity_id}`}>
                            <Button variant="outline" size="xs">
                              View
                            </Button>
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : myEfforts.length === 0 ? (
            <p className="text-sm text-muted-foreground">You have no efforts on this segment yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-xs text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4 text-left">Time</th>
                    <th className="py-2 pr-4 text-right">Avg speed</th>
                    <th className="py-2 pr-4 text-right">Date</th>
                    <th className="py-2 pr-4 text-right">Visibility</th>
                    <th className="py-2 pr-0 text-right">Activity</th>
                  </tr>
                </thead>
                <tbody>
                  {myEfforts.map((eff) => (
                    <tr key={eff.id} className="border-b last:border-0">
                      <td className="py-2 pr-4 align-middle">
                        {formatDuration(eff.effort_time_s)}
                        {eff.is_pr && (
                          <span className="ml-2 inline-flex items-center rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200 px-2 py-0.5 text-[10px] font-semibold">
                            PR
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-right align-middle">
                        {formatSpeed(eff.avg_speed_kmh)}
                      </td>
                      <td className="py-2 pr-4 text-right align-middle">
                        {formatDate(eff.started_at)}
                      </td>
                      <td className="py-2 pr-4 text-right align-middle capitalize">
                        {eff.visibility}
                      </td>
                      <td className="py-2 pr-0 text-right align-middle">
                        <Link href={`/activities/${eff.activity_id}`}>
                          <Button variant="outline" size="xs">
                            View
                          </Button>
                        </Link>
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

