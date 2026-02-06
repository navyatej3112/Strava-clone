"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { activitiesApi, likesApi, commentsApi, type ActivityDetail, type CommentItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  formatDistance,
  formatDuration,
  formatDate,
  formatPace,
  formatSpeed,
} from "@/lib/utils";
import { ActivityMap } from "@/components/activity-map";
import { Heart, MessageCircle, Loader2, Lock, AlertCircle } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { CardTitle } from "@/components/ui/card";

const POLL_INTERVAL_MS = 2000;

export default function ActivityDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { user: me } = useAuth();
  const [activity, setActivity] = useState<ActivityDetail | null>(null);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [commentText, setCommentText] = useState("");
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setForbidden(false);
    Promise.all([activitiesApi.get(id), commentsApi.list(id)])
      .then(([a, c]) => {
        if (!cancelled) {
          setActivity(a);
          setComments(c);
        }
      })
      .catch((err: Error & { status?: number }) => {
        if (!cancelled) {
          setActivity(null);
          setForbidden(err.status === 403);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  // Poll status when processing (e.g. after upload)
  useEffect(() => {
    if (!id || !me || activity?.status !== "processing") {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const st = await activitiesApi.getStatus(id);
        if (st.status === "ready" || st.status === "failed") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          const [a, c] = await Promise.all([activitiesApi.get(id), commentsApi.list(id)]);
          setActivity(a);
          setComments(c);
        }
      } catch {
        // ignore
      }
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [id, me, activity?.status]);

  async function toggleLike() {
    if (!activity) return;
    try {
      if (activity.liked_by_me) await likesApi.unlike(activity.id);
      else await likesApi.like(activity.id);
      setActivity((prev) =>
        prev
          ? {
              ...prev,
              liked_by_me: !prev.liked_by_me,
              like_count: prev.like_count + (prev.liked_by_me ? -1 : 1),
            }
          : null
      );
    } catch {}
  }

  async function submitComment(e: React.FormEvent) {
    e.preventDefault();
    if (!commentText.trim()) return;
    try {
      const c = await commentsApi.create(id, commentText.trim());
      setComments((prev) => [...prev, c]);
      setCommentText("");
      setActivity((prev) => (prev ? { ...prev, comment_count: prev.comment_count + 1 } : null));
    } catch {}
  }

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-muted rounded w-2/3" />
        <div className="h-64 bg-muted rounded" />
      </div>
    );
  }
  if (forbidden) {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <Lock className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground mb-4">This activity is private.</p>
          <div className="flex gap-3 justify-center">
            <Link href="/feed">
              <Button variant="outline">Back to feed</Button>
            </Link>
            <Link href="/profile">
              <Button>My profile</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }
  if (!activity) {
    return (
      <Card>
        <CardContent className="p-12 text-center text-muted-foreground">
          Activity not found.
        </CardContent>
      </Card>
    );
  }

  if (activity.status === "processing") {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <div>
                <h1 className="text-2xl font-bold">{activity.title}</h1>
                <p className="text-sm text-muted-foreground">Processing your upload…</p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="h-4 bg-muted rounded w-1/4 animate-pulse" />
              <div className="h-40 bg-muted rounded animate-pulse" />
              <p className="text-sm text-muted-foreground">We're computing distance, pace, and elevation. This usually takes a few seconds.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (activity.status === "failed") {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <h1 className="text-2xl font-bold">{activity.title}</h1>
            <p className="text-sm text-destructive font-medium">Processing failed</p>
          </CardHeader>
          <CardContent className="space-y-4">
            {activity.error_message && (
              <p className="text-sm text-muted-foreground">{activity.error_message}</p>
            )}
            <Link href="/activities/new">
              <Button>Upload again</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between space-y-0">
          <div>
            <Link href={`/profile/${activity.user_id}`} className="font-medium hover:underline">
              {activity.user?.name ?? "Unknown"}
            </Link>
            <h1 className="text-2xl font-bold mt-1">{activity.title}</h1>
            <p className="text-sm text-muted-foreground">{formatDate(activity.started_at)} · {activity.sport_type}</p>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {activity.rank_eligible === false && activity.sport_type === "run" && (
            <div className="flex items-center gap-2 rounded-md bg-muted/50 border border-muted px-3 py-2 text-sm text-muted-foreground">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>
                Excluded from PaceRank
                {activity.rank_excluded_reason && (
                  <span className="ml-1">
                    ({activity.rank_excluded_reason === "max_speed_too_high"
                      ? "max speed too high"
                      : activity.rank_excluded_reason === "avg_speed_too_high"
                        ? "avg speed too high"
                        : activity.rank_excluded_reason === "distance_time_unrealistic"
                          ? "distance/time unrealistic"
                          : activity.rank_excluded_reason === "too_short"
                            ? "too short"
                            : activity.rank_excluded_reason})
                  </span>
                )}
              </span>
            </div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Distance</p>
              <p className="font-medium">{formatDistance(activity.distance_m)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Duration</p>
              <p className="font-medium">{formatDuration(activity.duration_s)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Elevation</p>
              <p className="font-medium">{activity.elevation_gain_m != null ? `${activity.elevation_gain_m} m` : "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Calories</p>
              <p className="font-medium">{activity.calories ?? "—"}</p>
            </div>
          </div>
          {activity.polyline && (
            <div className="h-64 rounded-md overflow-hidden bg-muted">
              <ActivityMap polyline={activity.polyline} className="h-full w-full" />
            </div>
          )}
          {activity.segments && activity.segments.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Segments</h3>
              <div className="border rounded-md divide-y bg-muted/40">
                {activity.segments.map((seg) => (
                  <div key={seg.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <div className="flex flex-col">
                      <Link
                        href={`/segments/${seg.segment_id}`}
                        className="font-medium hover:underline"
                      >
                        {seg.segment_name ?? "Segment"}
                      </Link>
                      <span className="text-xs text-muted-foreground">
                        {formatDuration(seg.effort_time_s)} · {formatSpeed(seg.avg_speed_kmh)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {seg.is_pr && (
                        <span className="inline-flex items-center rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200 px-2 py-0.5 text-[10px] font-semibold">
                          PR
                        </span>
                      )}
                      {seg.is_kom && (
                        <span className="inline-flex items-center rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200 px-2 py-0.5 text-[10px] font-semibold">
                          KOM
                        </span>
                      )}
                      <Link href={`/segments/${seg.segment_id}`}>
                        <Button size="xs" variant="outline">
                          View
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {activity.splits && activity.splits.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Splits (per km)</h3>
              <ul className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                {activity.splits.map((s) => (
                  <li key={s.index} className="p-2 rounded bg-muted/50">
                    <span className="font-medium">#{s.index}</span> {formatDuration(s.duration_s)}
                    {s.pace_per_km_s != null && ` · ${formatPace(s.pace_per_km_s)}`}
                    {s.speed_kmh != null && ` · ${formatSpeed(s.speed_kmh)}`}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex items-center gap-4 pt-2" id="comments">
            <Button variant="ghost" size="sm" onClick={toggleLike}>
              <Heart className={`h-4 w-4 mr-1 ${activity.liked_by_me ? "fill-red-500 text-red-500" : ""}`} />
              {activity.like_count}
            </Button>
            <span className="text-sm text-muted-foreground">
              <MessageCircle className="h-4 w-4 inline mr-1" />
              {activity.comment_count} comments
            </span>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Comments</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {me && (
            <form onSubmit={submitComment} className="flex gap-2">
              <Input
                placeholder="Add a comment…"
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
              />
              <Button type="submit" size="sm">Post</Button>
            </form>
          )}
          {comments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No comments yet.</p>
          ) : (
            <ul className="space-y-3">
              {comments.map((c) => (
                <li key={c.id} className="flex gap-2 text-sm">
                  <Link href={`/profile/${c.user_id}`} className="font-medium hover:underline shrink-0">
                    {c.user?.name ?? "Unknown"}
                  </Link>
                  <span className="text-muted-foreground">{c.body}</span>
                  <span className="text-muted-foreground text-xs shrink-0">{formatDate(c.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
