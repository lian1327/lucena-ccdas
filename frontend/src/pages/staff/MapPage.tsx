/**
 * GIS dashboard (Module 5): heatmap, clustered reports, barangay load, and DBSCAN hotspots.
 * Lazy-loaded so Leaflet + plugins only download for staff who open the map.
 */
import "leaflet/dist/leaflet.css";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, ButtonGroup, Card, Form, ListGroup, Nav, ToggleButton } from "react-bootstrap";
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useNavigate } from "react-router-dom";

import { useBarangayStats, useHotspots, useMapPoints, type MapFilters } from "@/api/gis";
import { useCategories } from "@/api/public";
import type { BarangayStat, Hotspot } from "@/api/types";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { LGU_CENTER } from "@/config";
import { ClusterLayer, HeatLayer } from "@/features/gis/layers";
import { fmtDate } from "@/utils/format";

type LayerKey = "heat" | "markers" | "barangays" | "hotspots";
const LAYERS: { key: LayerKey; label: string; icon: string }[] = [
  { key: "heat", label: "Heatmap", icon: "fire" },
  { key: "markers", label: "Reports", icon: "geo-alt" },
  { key: "barangays", label: "Barangays", icon: "bullseye" },
  { key: "hotspots", label: "Hotspots", icon: "exclamation-octagon" },
];
const WINDOWS = [
  { days: 30, label: "30 araw" },
  { days: 90, label: "90 araw" },
  { days: 365, label: "1 taon" },
];

function FlyTo({ target }: { target: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo(target, 17, { duration: 0.8 });
  }, [map, target]);
  return null;
}

function openShare(b: BarangayStat) {
  return b.concerns ? b.open / b.concerns : 0;
}

function barangayColor(b: BarangayStat) {
  const s = openShare(b);
  return s > 0.3 ? "#d7191c" : s > 0.15 ? "#fdae61" : "#1a9641";
}

export function MapPage() {
  const navigate = useNavigate();
  const categories = useCategories();
  const [filters, setFilters] = useState<MapFilters>({ days: 365, status: "all" });
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({ heat: true, markers: false, barangays: false, hotspots: true });
  const [side, setSide] = useState<"hotspots" | "barangays">("hotspots");
  const [target, setTarget] = useState<[number, number] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  const points = useMapPoints(filters);
  const brgys = useBarangayStats(filters);
  const hot = useHotspots(filters);
  const openCase = useCallback((id: number) => navigate(`/staff/cases/${id}`), [navigate]);
  const pts = useMemo(() => points.data?.points ?? [], [points.data]);
  const maxConcerns = Math.max(1, ...(brgys.data ?? []).map((b) => b.concerns));

  const set = <K extends keyof MapFilters>(k: K, v: MapFilters[K]) => setFilters((f) => ({ ...f, [k]: v }));
  const fly = (lat: number | null | undefined, lng: number | null | undefined, idx?: number) => {
    if (lat == null || lng == null) return;
    setTarget([lat, lng]);
    setSelected(idx ?? null);
  };
  const loading = points.isFetching || brgys.isFetching || hot.isFetching;

  return (
    <div className="d-flex flex-column gap-2" style={{ minHeight: "calc(100vh - 120px)" }}>
      <div className="d-flex flex-wrap align-items-center gap-2">
        <h1 className="h4 fw-bold mb-0 me-2">GIS Map</h1>
        <ButtonGroup size="sm">
          {WINDOWS.map((w) => (
            <ToggleButton key={w.days} id={`win-${w.days}`} type="radio" variant="outline-secondary" value={w.days}
              checked={filters.days === w.days} onChange={() => set("days", w.days)}>{w.label}</ToggleButton>
          ))}
        </ButtonGroup>
        <Form.Select size="sm" style={{ width: 190 }} value={filters.category ?? ""} aria-label="Kategorya"
          onChange={(e) => set("category", e.target.value || undefined)}>
          <option value="">Lahat ng kategorya</option>
          {categories.data?.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
        </Form.Select>
        <Form.Select size="sm" style={{ width: 140 }} value={filters.status} aria-label="Status"
          onChange={(e) => set("status", e.target.value as MapFilters["status"])}>
          <option value="all">Lahat ng status</option>
          <option value="open">Bukas lang</option>
          <option value="resolved">Naayos na</option>
        </Form.Select>
        <Form.Select size="sm" style={{ width: 130 }} value={filters.priority ?? ""} aria-label="Priority"
          onChange={(e) => set("priority", e.target.value || undefined)}>
          <option value="">Lahat ng antas</option>
          {["P1", "P2", "P3", "P4"].map((p) => <option key={p}>{p}</option>)}
        </Form.Select>
        <div className="ms-lg-auto d-flex flex-wrap gap-1">
          {LAYERS.map((l) => (
            <ToggleButton key={l.key} id={`layer-${l.key}`} type="checkbox" size="sm" variant="outline-primary" value={l.key}
              checked={layers[l.key]} onChange={() => setLayers((s) => ({ ...s, [l.key]: !s[l.key] }))}>
              <i className={`bi bi-${l.icon} me-1`} aria-hidden />{l.label}
            </ToggleButton>
          ))}
        </div>
      </div>

      <div className="small text-secondary">
        {points.data && (
          <>
            {points.data.total} reports · {points.data.points.length} naka-pin sa mapa
            {points.data.unpinned > 0 && <> · {points.data.unpinned} walang pin (kasama sa Barangays layer)</>}
          </>
        )}
        {loading && <span className="ms-2 spinner-border spinner-border-sm" role="status" />}
      </div>

      <div className="d-flex flex-column flex-lg-row gap-3 flex-grow-1">
        <Card className="border-0 shadow-sm flex-grow-1 overflow-hidden" style={{ minHeight: 480 }}>
          {points.isLoading ? <FullPageSpinner label="Nilo-load ang mapa…" /> : (
            <MapContainer center={LGU_CENTER} zoom={13} style={{ height: "100%", minHeight: 480 }}>
              <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <FlyTo target={target} />
              {layers.heat && <HeatLayer points={pts} />}
              {layers.markers && <ClusterLayer points={pts} onOpen={openCase} />}
              {layers.barangays && brgys.data?.filter((b) => b.lat != null).map((b) => (
                <CircleMarker key={b.id} center={[b.lat!, b.lng!]} radius={8 + 22 * Math.sqrt(b.concerns / maxConcerns)}
                  pathOptions={{ color: barangayColor(b), fillColor: barangayColor(b), fillOpacity: 0.35, weight: 2 }}>
                  <Tooltip direction="top">
                    <strong>{b.name}</strong><br />
                    {b.concerns} concerns · {b.open} bukas{b.overdue ? ` · ${b.overdue} overdue` : ""}<br />
                    {b.per_10k != null && <>{b.per_10k} bawat 10k residente<br /></>}
                    Top: {b.top_issues[0]?.name}
                  </Tooltip>
                </CircleMarker>
              ))}
              {layers.hotspots && hot.data?.hotspots.map((h, i) => (
                <Circle key={`${h.lat},${h.lng}`} center={[h.lat, h.lng]} radius={Math.max(40, h.radius_m)}
                  pathOptions={{ color: selected === i ? "#000" : "#e8590c", fillColor: "#fd7e14", fillOpacity: 0.25,
                    weight: selected === i ? 4 : 2, dashArray: h.open ? undefined : "6 4" }}>
                  <Tooltip direction="top" permanent={selected === i}>
                    <strong>{h.top_issue}</strong> · {h.count} problema
                  </Tooltip>
                  <Popup><HotspotDetail h={h} onOpen={openCase} /></Popup>
                </Circle>
              ))}
            </MapContainer>
          )}
        </Card>

        <Card className="border-0 shadow-sm" style={{ width: "100%", maxWidth: 380 }}>
          <Card.Header className="bg-white">
            <Nav variant="pills" className="small">
              <Nav.Item><Nav.Link active={side === "hotspots"} onClick={() => setSide("hotspots")}>
                Hotspots {hot.data && <Badge bg="secondary">{hot.data.hotspots.length}</Badge>}
              </Nav.Link></Nav.Item>
              <Nav.Item><Nav.Link active={side === "barangays"} onClick={() => setSide("barangays")}>Barangays</Nav.Link></Nav.Item>
            </Nav>
          </Card.Header>
          <div style={{ maxHeight: 560, overflowY: "auto" }}>
            {side === "hotspots" ? (
              <>
                <div className="small text-secondary px-3 pt-2">
                  Paulit-ulit na problema sa iisang lugar (≥{hot.data?.min_samples ?? 4} reports sa loob ng
                  {" "}{hot.data?.eps_m ?? 75} m). Ang "buwan" ay ilang buwan itong inirereklamo.
                </div>
                <ListGroup variant="flush">
                  {hot.data?.hotspots.length === 0 && <ListGroup.Item className="small text-secondary">Walang hotspot sa filter na ito.</ListGroup.Item>}
                  {hot.data?.hotspots.map((h, i) => (
                    <ListGroup.Item key={`${h.lat},${h.lng}`} action active={selected === i} onClick={() => fly(h.lat, h.lng, i)} className="small">
                      <div className="d-flex justify-content-between gap-2">
                        <span className="fw-semibold">{h.top_issue}</span>
                        <Badge bg={h.open ? "danger" : "success"}>{h.open ? `${h.open} bukas` : "naayos"}</Badge>
                      </div>
                      <div>{h.barangay}{h.landmark && ` · ${h.landmark}`}</div>
                      <div className={selected === i ? "" : "text-secondary"}>
                        {h.count} problema · {h.reports} reports · {h.months_active} buwan · {h.top_issue_share}% iisang isyu
                      </div>
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              </>
            ) : (
              <ListGroup variant="flush">
                {brgys.data?.map((b) => (
                  <ListGroup.Item key={b.id} action onClick={() => { fly(b.lat, b.lng); setLayers((l) => ({ ...l, barangays: true })); }} className="small">
                    <div className="d-flex justify-content-between">
                      <span className="fw-semibold">{b.name}</span>
                      <span>{b.concerns}</span>
                    </div>
                    <div className="text-secondary">
                      {b.open} bukas{b.overdue ? ` · ${b.overdue} overdue` : ""}
                      {b.per_10k != null && ` · ${b.per_10k}/10k`}
                      {b.median_days_to_resolve != null && ` · ${b.median_days_to_resolve} araw median`}
                    </div>
                    <div className="text-secondary">Top: {b.top_issues.map((t) => `${t.name} (${t.count})`).join(", ")}</div>
                  </ListGroup.Item>
                ))}
              </ListGroup>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function HotspotDetail({ h, onOpen }: { h: Hotspot; onOpen: (id: number) => void }) {
  return (
    <div className="small" style={{ minWidth: 220 }}>
      <div className="fw-semibold">{h.top_issue} · {h.barangay}</div>
      {h.landmark && <div className="text-secondary">{h.landmark}</div>}
      <div className="mt-1">{h.count} problema · {h.reports} reports · {h.open} bukas</div>
      <div>Aktibo {h.months_active} buwan: {fmtDate(h.first_report)} – {fmtDate(h.last_report)}</div>
      <ul className="mb-1 ps-3">{h.issues.map((x) => <li key={x.name}>{x.name}: {x.count}</li>)}</ul>
      <div className="d-flex flex-wrap gap-1">
        {h.concern_ids.slice(0, 6).map((id) => (
          <button key={id} type="button" className="btn btn-sm btn-outline-primary py-0" onClick={() => onOpen(id)}>#{id}</button>
        ))}
      </div>
    </div>
  );
}

export default MapPage;
