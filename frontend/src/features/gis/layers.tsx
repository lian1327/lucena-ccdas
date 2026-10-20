/**
 * Imperative Leaflet layers (heatmap, marker clusters) wrapped as components. react-leaflet has no
 * built-in wrappers for these plugins, so we manage them through useMap().
 */
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "leaflet.heat";

import L from "leaflet";
import { useEffect } from "react";
import { useMap } from "react-leaflet";

import type { MapPoint } from "@/api/types";

export function HeatLayer({ points }: { points: MapPoint[] }) {
  const map = useMap();
  useEffect(() => {
    const max = Math.max(3, ...points.map((p) => p.reports));
    const layer = L.heatLayer(
      points.map((p) => [p.lat, p.lng, Math.min(1, 0.35 + p.reports / max)] as [number, number, number]),
      { radius: 22, blur: 18, maxZoom: 16, minOpacity: 0.35,
        gradient: { 0.3: "#2c7bb6", 0.5: "#abd9e9", 0.65: "#ffffbf", 0.8: "#fdae61", 1: "#d7191c" } },
    );
    layer.addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, points]);
  return null;
}

const STATUS_COLOR = (p: MapPoint) =>
  p.overdue ? "#8b0000" : ["resolved", "closed"].includes(p.status) ? "#198754" : "#dc3545";

export function ClusterLayer({ points, onOpen }: { points: MapPoint[]; onOpen: (id: number) => void }) {
  const map = useMap();
  useEffect(() => {
    const group = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 45, chunkedLoading: true });
    for (const p of points) {
      const m = L.circleMarker([p.lat, p.lng], {
        radius: 6 + Math.min(6, p.reports - 1), color: "#fff", weight: 1.5,
        fillColor: STATUS_COLOR(p), fillOpacity: 0.9,
      });
      const div = document.createElement("div");
      div.className = "small";
      div.innerHTML = `
        <div class="fw-semibold">${escapeHtml(p.subcategory ?? "—")}</div>
        <div class="text-secondary">${escapeHtml(p.barangay)} · ${p.ref}</div>
        <div>${p.status.replace("_", " ")}${p.priority ? ` · ${p.priority}` : ""}${p.overdue ? " · <b class='text-danger'>overdue</b>" : ""}</div>
        <div>${p.reports} ${p.reports > 1 ? "residents reported" : "report"}</div>`;
      const btn = document.createElement("button");
      btn.className = "btn btn-sm btn-primary mt-1";
      btn.textContent = "Buksan ang kaso";
      btn.onclick = () => onOpen(p.id);
      div.appendChild(btn);
      m.bindPopup(div);
      group.addLayer(m);
    }
    map.addLayer(group);
    return () => {
      map.removeLayer(group);
    };
  }, [map, points, onOpen]);
  return null;
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
