"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { segmentsApi, type SegmentCreate } from "@/lib/api";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";

export default function NewSegmentPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [form, setForm] = useState<SegmentCreate>({
    name: "",
    description: "",
    polyline: "",
    is_public: true,
  });
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.polyline.trim()) {
      toast("Name and polyline are required.", "error");
      return;
    }
    setSubmitting(true);
    try {
      const created = await segmentsApi.create({
        name: form.name.trim(),
        description: form.description?.trim() || undefined,
        polyline: form.polyline.trim(),
        is_public: form.is_public,
      });
      toast("Segment created.", "success");
      router.push(`/segments/${created.id}`);
    } catch (err) {
      console.error(err);
      toast("Failed to create segment.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-bold">Create Segment</h1>
          <p className="text-sm text-muted-foreground">
            Create a segment from an existing encoded polyline. You can copy polylines from existing activities or mapping tools.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Waterfront Loop"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="description">Description (optional)</Label>
              <Textarea
                id="description"
                value={form.description ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Short description of the segment…"
                rows={3}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="polyline">Polyline</Label>
              <Textarea
                id="polyline"
                value={form.polyline}
                onChange={(e) => setForm((f) => ({ ...f, polyline: e.target.value }))}
                placeholder="Encoded polyline string…"
                rows={4}
              />
              <p className="text-xs text-muted-foreground">
                Paste an encoded polyline (e.g. from an existing activity route or an external tool).
              </p>
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="space-y-1">
                <Label htmlFor="is_public">Public segment</Label>
                <p className="text-xs text-muted-foreground">
                  Public segments appear in browse and leaderboards. Private segments are visible only to you.
                </p>
              </div>
              <Switch
                id="is_public"
                checked={form.is_public}
                onCheckedChange={(checked) => setForm((f) => ({ ...f, is_public: checked }))}
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating…" : "Create segment"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

