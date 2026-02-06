"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { activitiesApi } from "@/lib/api";

const SPORT_TYPES = ["run", "ride", "walk"] as const;
const VISIBILITY = ["public", "followers", "private"] as const;

export default function NewActivityPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [sportType, setSportType] = useState<"run" | "ride" | "walk">("run");
  const [visibility, setVisibility] = useState<"public" | "followers" | "private">("public");
  const [startedAt, setStartedAt] = useState(() => new Date().toISOString().slice(0, 16));
  const [polyline, setPolyline] = useState("");
  const [distanceM, setDistanceM] = useState("");
  const [durationS, setDurationS] = useState("");
  const [elevationGainM, setElevationGainM] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const form = new FormData();
      form.append("title", title);
      form.append("sport_type", sportType);
      form.append("visibility", visibility);
      form.append("started_at", new Date(startedAt).toISOString());
      if (polyline) form.append("polyline", polyline);
      if (distanceM) form.append("distance_m", distanceM);
      if (durationS) form.append("duration_s", durationS);
      if (elevationGainM) form.append("elevation_gain_m", elevationGainM);
      if (file) form.append("file", file);
      const activity = await activitiesApi.create(form);
      router.push(`/activities/${activity.id}` + (activity.status === "processing" ? "?processing=1" : ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create activity");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>Create activity</CardTitle>
        <p className="text-sm text-muted-foreground">Add a run, ride, or walk. Upload GPX/TCX or enter details manually.</p>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" placeholder="Morning run" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Sport type</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={sportType}
                onChange={(e) => setSportType(e.target.value as "run" | "ride" | "walk")}
              >
                {SPORT_TYPES.map((s) => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Visibility</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={visibility}
                onChange={(e) => setVisibility(e.target.value as "public" | "followers" | "private")}
              >
                {VISIBILITY.map((v) => (
                  <option key={v} value={v}>{v.charAt(0).toUpperCase() + v.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="started_at">Start time</Label>
            <Input id="started_at" type="datetime-local" value={startedAt} onChange={(e) => setStartedAt(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="file">Upload GPX or TCX (optional)</Label>
            <Input
              id="file"
              type="file"
              accept=".gpx,.tcx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="polyline">Or paste encoded polyline (optional)</Label>
            <Input
              id="polyline"
              placeholder="Encoded polyline string"
              value={polyline}
              onChange={(e) => setPolyline(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="distance_m">Distance (m)</Label>
              <Input id="distance_m" type="number" min="0" step="1" placeholder="5000" value={distanceM} onChange={(e) => setDistanceM(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="duration_s">Duration (s)</Label>
              <Input id="duration_s" type="number" min="0" placeholder="1800" value={durationS} onChange={(e) => setDurationS(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="elevation_gain_m">Elevation gain (m)</Label>
              <Input id="elevation_gain_m" type="number" min="0" step="0.1" placeholder="100" value={elevationGainM} onChange={(e) => setElevationGainM(e.target.value)} />
            </div>
          </div>
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Creating…" : "Create activity"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
