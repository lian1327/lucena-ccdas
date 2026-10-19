/**
 * Optional map pin. Lazy-loaded so citizens who skip it never download Leaflet or map tiles.
 */
import "leaflet/dist/leaflet.css";

import L from "leaflet";
import iconRetina from "leaflet/dist/images/marker-icon-2x.png";
import icon from "leaflet/dist/images/marker-icon.png";
import shadow from "leaflet/dist/images/marker-shadow.png";
import { useEffect } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";

L.Icon.Default.mergeOptions({ iconRetinaUrl: iconRetina, iconUrl: icon, shadowUrl: shadow });

export type LatLng = { lat: number; lng: number };

type Props = {
  center: [number, number];
  value: LatLng | null;
  onChange: (v: LatLng) => void;
};

function ClickToPin({ onChange }: { onChange: (v: LatLng) => void }) {
  useMapEvents({ click: (e) => onChange({ lat: e.latlng.lat, lng: e.latlng.lng }) });
  return null;
}

function Recenter({ center, value }: { center: [number, number]; value: LatLng | null }) {
  const map = useMap();
  useEffect(() => {
    map.setView(value ? [value.lat, value.lng] : center, value ? 18 : 15);
  }, [map, center, value]);
  return null;
}

export default function LocationPicker({ center, value, onChange }: Props) {
  return (
    <MapContainer center={center} zoom={15} style={{ height: 260 }} className="rounded border">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickToPin onChange={onChange} />
      <Recenter center={center} value={value} />
      {value && (
        <Marker
          position={[value.lat, value.lng]}
          draggable
          eventHandlers={{
            dragend: (e) => {
              const p = (e.target as L.Marker).getLatLng();
              onChange({ lat: p.lat, lng: p.lng });
            },
          }}
        />
      )}
    </MapContainer>
  );
}
