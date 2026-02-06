"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { usersApi, activitiesApi, followsApi, type ActivityItem, type UserPublic } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatDistance, formatDuration, formatDate } from "@/lib/utils";
import { ActivityMap } from "@/components/activity-map";
import { ProfileStats } from "@/components/profile-stats";
import { useAuth } from "@/lib/auth-context";

export default function PublicProfilePage() {
  const params = useParams();
  const id = params.id as string;
  const { user: me } = useAuth();
  const [profile, setProfile] = useState<UserPublic | null>(null);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [following, setFollowing] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    if (!id) return;
    setForbidden(false);
    Promise.all([usersApi.get(id), activitiesApi.listByUser(id)])
      .then(([u, list]) => {
        setProfile(u);
        setActivities(list);
      })
      .catch((err: Error & { status?: number }) => {
        setProfile(null);
        setForbidden(err.status === 403);
      })
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!me || !id || me.id === id) {
      setFollowing(null);
      return;
    }
    followsApi
      .isFollowing(id)
      .then(setFollowing)
      .catch(() => setFollowing(false));
  }, [me, id]);

  async function toggleFollow() {
    if (!profile || !me || me.id === id) return;
    try {
      if (following) {
        await followsApi.unfollow(id);
        setFollowing(false);
      } else {
        await followsApi.follow(id);
        setFollowing(true);
      }
    } catch {}
  }

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-20 bg-muted rounded w-1/2" />
        <div className="h-32 bg-muted rounded" />
      </div>
    );
  }
  if (forbidden) {
    return (
      <Card>
        <CardContent className="p-12 text-center text-muted-foreground">
          <p>This profile is private.</p>
        </CardContent>
      </Card>
    );
  }
  if (!profile) {
    return (
      <Card>
        <CardContent className="p-12 text-center text-muted-foreground">
          User not found.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <ProfileStats userId={id} />
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-full bg-primary/20 flex items-center justify-center text-2xl font-bold text-primary">
                {profile.name.charAt(0)}
              </div>
              <div>
                <h1 className="text-2xl font-bold">{profile.name}</h1>
                {profile.bio && <p className="text-muted-foreground">{profile.bio}</p>}
              </div>
            </div>
            {me && me.id !== id && following !== null && (
              <Button variant={following ? "outline" : "default"} onClick={toggleFollow}>
                {following ? "Unfollow" : "Follow"}
              </Button>
            )}
          </div>
        </CardHeader>
      </Card>
      <h2 className="text-xl font-semibold">Activities</h2>
      {activities.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            No activities yet.
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
