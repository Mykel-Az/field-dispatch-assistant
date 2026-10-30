import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MapContainer, Marker, TileLayer, useMap } from 'react-leaflet';
import type { MapPin } from '../api/client';
import StatusPin from '../components/StatusPin';
import { isJobStatus } from '../status';

const US_CENTER: [number, number] = [39.8, -98.6];

const iconCache = new Map<string, L.DivIcon>();
function iconFor(status: string, selected: boolean) {
  const key = `${status}|${selected}`;
  let icon = iconCache.get(key);
  if (!icon) {
    const size = selected ? 40 : 30;
    icon = L.divIcon({
      className: '',
      iconSize: [(size * 18) / 22, size],
      iconAnchor: [(size * 9) / 22, size - 2],
      html: isJobStatus(status) ? renderToStaticMarkup(<StatusPin status={status} size={size} />) : '',
    });
    iconCache.set(key, icon);
  }
  return icon;
}

/** Fit the view to the pins, but only when the set of pins changes, not on every poll. */
function FitToPins({ pins }: { pins: MapPin[] }) {
  const map = useMap();
  const key = pins.map((p) => p.id).join(',');
  useEffect(() => {
    if (pins.length === 0) return;
    const bounds = L.latLngBounds(pins.map((p) => [p.lat, p.lng] as [number, number]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refit only when the ids change
  }, [map, key]);
  return null;
}

interface Props {
  pins: MapPin[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  height?: number | string;
}

export default function JobsMap({ pins, selectedId, onSelect, height = 520 }: Props) {
  const ordered = useMemo(
    // the selected pin is drawn last, so it sits on top
    () => [...pins].sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId)),
    [pins, selectedId],
  );
  return (
    <div className="overflow-hidden rounded-xl border border-line" style={{ height }}>
      <MapContainer center={US_CENTER} zoom={4} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitToPins pins={pins} />
        {ordered.map((p) => (
          <Marker
            key={p.id}
            position={[p.lat, p.lng]}
            icon={iconFor(p.status, p.id === selectedId)}
            eventHandlers={{ click: () => onSelect(p.id) }}
          />
        ))}
      </MapContainer>
    </div>
  );
}
