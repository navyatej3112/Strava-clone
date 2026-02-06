"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { segmentsApi, type SegmentResponse } from "@/lib/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { formatDistance } from "@/lib/utils";

export default function SegmentsPage() {
  const [segments, setSegments] = useState<SegmentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    setError(false);
    const t = setTimeout(() => {
      segmentsApi
        .list({ query: query || undefined, limit: 20, offset: 0 })
        .then(setSegments)
        .catch(() => {
          setError(true);
          setSegments([]);
        })
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Segments</h1>
        <Link href="/segments/new">
          <Button>Create segment</Button>
        </Link>
      </div>
      <div className="flex items-center gap-3">
        <Input
          placeholder="Search segments…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="max-w-sm"
        />
      </div>
      {loading ? (
        <div className="space-y-2">
          {[...Array(4)].map((_, idx) => (
            <div key={idx} className="h-20 rounded-md bg-muted animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <p className="text-sm text-muted-foreground">Unable to load segments.</p>
      ) : segments.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            <p>No segments found.</p>
            <p className="text-xs mt-2">Create one from an existing route polyline to get started.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {segments.map((s) => (
            <Card key={s.id}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <div>
                  <h2 className="font-semibold">{s.name}</h2>
                  {s.description && (
                    <p className="text-xs text-muted-foreground line-clamp-2 mt-1">{s.description}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatDistance(s.distance_m)} · {s.is_public ? "Public" : "Private"}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      s.is_public ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {s.is_public ? "Public" : "Private"}
                  </span>
                  <Link href={`/segments/${s.id}`}>
                    <Button size="sm" variant="outline">
                      View
                    </Button>
                  </Link>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

