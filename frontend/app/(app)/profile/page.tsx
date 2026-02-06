"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import Link from "next/link";
import { activitiesApi, type ActivityItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatDistance, formatDuration, formatDate } from "@/lib/utils";
import { ActivityMap } from "@/components/activity-map";
import { ProfileStats } from "@/components/profile-stats";

export default function ProfilePage() {
  const { user } = useAuth();
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    activitiesApi
      .listByUser(user.id)
      .then(setActivities)
      .catch(() => setActivities([]))
      .finally(() => setLoading(false));
  }, [user?.id]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <ProfileStats userId={undefined} />
      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 rounded-full bg-primary/20 flex items-center justify-center text-2xl font-bold text-primary">
              {user.name.charAt(0)}
            </div>
            <div>
              <h1 className="text-2xl font-bold">{user.name}</h1>
              <p className="text-muted-foreground">{user.email}</p>
              {user.bio && <p className="mt-1 text-sm">{user.bio}</p>}
            </div>
          </div>
          <Link href="/profile/edit">
            <Button variant="outline" size="sm">Edit profile</Button>
          </Link>
        </CardHeader>
      </Card>
      <h2 className="text-xl font-semibold">Your activities</h2>
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="h-5 bg-muted rounded w-1/3 mb-3" />
                <div className="h-4 bg-muted rounded w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : activities.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            <p>No activities yet.</p>
            <Link href="/activities/new">
              <Button className="mt-4">Create your first activity</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-4">
          {activities.map((a) => (
            <Card key={a.id}>
              <CardHeader className="pb-2">
                <Link href={`/activities/${a.id}`}>
                  <h3 className="font-semibold text-lg hover:underline">{a.title}</h3>
                </Link>
                <p className="text-sm text-muted-foreground">{formatDate(a.started_at)} · {a.sport_type}</p>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex flex-wrap gap-4 text-sm text-muted-foreground mb-3">
                  <span>{formatDistance(a.distance_m)}</span>
                  <span>{formatDuration(a.duration_s)}</span>
                </div>
                {a.polyline && (
                  <div className="h-40 rounded-md overflow-hidden bg-muted">
                    <ActivityMap polyline={a.polyline} />
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </ul>
      )}
    </div>
  );
}
