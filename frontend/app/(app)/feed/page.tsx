"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { activitiesApi, likesApi, type ActivityItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatDistance, formatDuration, formatDate } from "@/lib/utils";
import { Heart, MessageCircle } from "lucide-react";
import { ActivityMap } from "@/components/activity-map";

export default function FeedPage() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sportFilter, setSportFilter] = useState<string | null>(null);

  useEffect(() => {
    activitiesApi
      .feed(sportFilter ? { sport_type: sportFilter } : undefined)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [sportFilter]);

  async function toggleLike(a: ActivityItem) {
    try {
      if (a.liked_by_me) await likesApi.unlike(a.id);
      else await likesApi.like(a.id);
      setItems((prev) =>
        prev.map((x) =>
          x.id === a.id
            ? {
                ...x,
                liked_by_me: !x.liked_by_me,
                like_count: x.like_count + (x.liked_by_me ? -1 : 1),
              }
            : x
        )
      );
    } catch {}
  }

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-6">
              <div className="h-6 bg-muted rounded w-1/3 mb-4" />
              <div className="h-4 bg-muted rounded w-2/3" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold">Feed</h1>
        <div className="flex gap-2">
          {["run", "ride", "walk"].map((s) => (
            <Button
              key={s}
              variant={sportFilter === s ? "default" : "outline"}
              size="sm"
              onClick={() => setSportFilter(sportFilter === s ? null : s)}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </Button>
          ))}
        </div>
      </div>
      {items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            <p>No activities in your feed yet.</p>
            <p className="mt-2 text-sm">Follow users or create your first activity.</p>
            <Link href="/activities/new">
              <Button className="mt-4">Create activity</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-4">
          {items.map((a) => (
            <Card key={a.id}>
              <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
                <div className="flex items-center gap-2">
                  <Link href={`/profile/${a.user_id}`} className="font-medium hover:underline">
                    {a.user?.name ?? "Unknown"}
                  </Link>
                  <span className="text-sm text-muted-foreground">· {formatDate(a.started_at)}</span>
                </div>
                <span className="text-xs uppercase text-muted-foreground">{a.sport_type}</span>
              </CardHeader>
              <CardContent className="pt-0 space-y-3">
                <Link href={`/activities/${a.id}`} className="block">
                  <h3 className="font-semibold text-lg hover:underline">{a.title}</h3>
                </Link>
                <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                  <span>{formatDistance(a.distance_m)}</span>
                  <span>{formatDuration(a.duration_s)}</span>
                  {a.elevation_gain_m != null && <span>{Number(a.elevation_gain_m)} m gain</span>}
                </div>
                {a.polyline && (
                  <div className="h-40 rounded-md overflow-hidden bg-muted">
                    <ActivityMap polyline={a.polyline} />
                  </div>
                )}
                <div className="flex items-center gap-4 pt-2">
                  <Button variant="ghost" size="sm" onClick={() => toggleLike(a)}>
                    <Heart className={`h-4 w-4 mr-1 ${a.liked_by_me ? "fill-red-500 text-red-500" : ""}`} />
                    {a.like_count}
                  </Button>
                  <Link href={`/activities/${a.id}#comments`}>
                    <Button variant="ghost" size="sm">
                      <MessageCircle className="h-4 w-4 mr-1" />
                      {a.comment_count}
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </ul>
      )}
    </div>
  );
}
