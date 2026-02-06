"use client";

import { useEffect, useRef } from "react";
import { decodePolyline } from "@/lib/polyline";

type Props = { polyline: string; className?: string };

export function ActivityMap({ polyline, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !polyline) return;
    const coords = decodePolyline(polyline);
    if (coords.length < 2) return;
    let map: import("maplibre-gl").Map | null = null;
    import("maplibre-gl").then((maplibre) => {
      const [lng, lat] = coords[Math.floor(coords.length / 2)];
      map = new maplibre.Map({
        container: containerRef.current!,
        style: "https://demotiles.maplibre.org/style.json",
        center: [lng, lat],
        zoom: 12,
      });
      map.on("load", () => {
        if (!map) return;
        map.addSource("route", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: coords.map(([lat, lon]) => [lon, lat]) },
          },
        });
        map.addLayer({
          id: "route",
          type: "line",
          source: "route",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "#22c55e", "line-width": 3 },
        });
        const lngs = coords.map((c) => c[1]);
        const lats = coords.map((c) => c[0]);
        map.fitBounds(
          [
            [Math.min(...lngs) - 0.005, Math.min(...lats) - 0.005],
            [Math.max(...lngs) + 0.005, Math.max(...lats) + 0.005],
          ],
          { padding: 24 }
        );
      });
    });
    return () => {
      map?.remove();
    };
  }, [polyline]);

  return <div ref={containerRef} className={className ?? "w-full h-full min-h-[160px]"} />;
}
