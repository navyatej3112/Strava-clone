"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { notificationsApi, type NotificationItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useToast } from "@/lib/toast-context";

function timeAgo(iso: string): string {
  const d = new Date(iso);
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "Just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 604800) return `${Math.floor(sec / 86400)}d ago`;
  return d.toLocaleDateString();
}

function typeLabel(
  t: string,
  data?: { new_tier_name?: string; segment_name?: string; type?: "pr" | "kom" } | null,
): string {
  if (t === "follow") return "followed you";
  if (t === "like") return "liked your activity";
  if (t === "comment") return "commented on your activity";
  if (t === "rank_up" && data?.new_tier_name) return `Rank Up! You reached ${data.new_tier_name}`;
  if (t === "rank_up") return "Rank Up!";
  if (t === "segment_pr") {
    return data?.segment_name ? `New PR on ${data.segment_name}` : "New segment PR";
  }
  if (t === "segment_kom") {
    return data?.segment_name ? `KOM! You're #1 on ${data.segment_name}` : "New segment KOM";
  }
  return t;
}

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    notificationsApi
      .list()
      .then((list) => {
        setItems(list);
        const unread = list.filter((n) => !n.is_read);
        if (unread.length > 0) {
          notificationsApi.markRead({ ids: unread.map((n) => n.id) }).catch(() => {});
        }
      })
      .catch(() => {
        setItems([]);
        toast("Failed to load notifications", "error");
      })
      .finally(() => setLoading(false));
  }, [toast]);

  async function markAllRead() {
    try {
      await notificationsApi.markRead({ mark_all: true });
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      toast("All marked as read", "success");
    } catch {
      toast("Failed to mark as read", "error");
    }
  }

  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-4">
              <div className="h-4 bg-muted rounded w-3/4" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Notifications</h1>
        {items.some((n) => !n.is_read) && (
          <Button variant="outline" size="sm" onClick={markAllRead}>
            Mark all as read
          </Button>
        )}
      </div>
      {items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            No notifications yet.
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-2">
          {items.map((n) => (
            <Card key={n.id} className={n.is_read ? "opacity-80" : ""}>
              <CardContent className="p-4">
                <Link
                  href={
                    n.type === "rank_up"
                      ? "/profile"
                      : n.type === "follow"
                        ? `/profile/${n.actor_user_id}`
                        : n.type === "segment_pr" || n.type === "segment_kom"
                          ? n.data?.segment_id
                            ? `/segments/${n.data.segment_id}`
                            : "#"
                          : n.activity_id
                            ? `/activities/${n.activity_id}`
                            : "#"
                  }
                  className="block hover:bg-muted/50 -m-4 p-4 rounded-md transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      {n.type === "rank_up" ? (
                        <span className="text-muted-foreground">{typeLabel(n.type, n.data)}</span>
                      ) : n.type === "segment_pr" || n.type === "segment_kom" ? (
                        <span className="text-muted-foreground">{typeLabel(n.type, n.data)}</span>
                      ) : (
                        <>
                          <span className="font-medium">{n.actor_name ?? "Someone"}</span>{" "}
                          <span className="text-muted-foreground">{typeLabel(n.type)}</span>
                        </>
                      )}
                    </div>
                    <span className="text-sm text-muted-foreground shrink-0">{timeAgo(n.created_at)}</span>
                  </div>
                </Link>
              </CardContent>
            </Card>
          ))}
        </ul>
      )}
    </div>
  );
}
