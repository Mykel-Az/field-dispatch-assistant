import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo } from 'react';
import { MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet';
import OfficeMarker from '../../shared/map/OfficeMarker';
import type { LatLng } from '../../shared/map/PinMap';
import { allPoints, type PlanMapData } from './planMapModel';

const US_CENTER: [number, number] = [39.8, -98.6];

const numberIcon = (n: number, color: string, selected: boolean) => {
  const size = selected ? 40 : 30;
  return L.divIcon({
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};color:#fff;
      border:2px solid #fff;box-shadow:${selected ? `0 0 0 3px #2a2622,` : ''}0 1px 4px rgba(0,0,0,.5);
      display:flex;align-items:center;justify-content:center;font:700 ${selected ? 16 : 14}px/1 system-ui">${n}</div>`,
  });
};

// A job nobody could take: white with a dashed amber edge and "!", so it is not
// mistaken for a stop (shape and glyph, not only colour).
const missIcon = (selected: boolean) => {
  const size = selected ? 38 : 28;
  return L.divIcon({
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:#fff;color:#92400e;
      border:2px dashed #92400e;${selected ? 'box-shadow:0 0 0 3px #2a2622;' : ''}
      display:flex;align-items:center;justify-content:center;font:700 15px/1 system-ui">!</div>`,
  });
};

/** Fit the view when the set of points changes, not on every selection. */
function Fit({ points, signature }: { points: [number, number][]; signature: string }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15 });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refit only when the points change
  }, [map, signature]);
  return null;
}

/** Bring the selected job into view if choosing it on a card moved it off screen. */
function Reveal({ at }: { at: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (at && !map.getBounds().contains(at)) map.panTo(at);
  }, [map, at]);
  return null;
}

interface Props {
  data: PlanMapData;
  office: LatLng | null;
  selectedId: number | null;
  onSelect: (jobId: number) => void;
  height?: number | string;
}

/**
 * The day on a map: the office, each technician's stops numbered in driving order
 * and joined by a line in their colour, and the jobs left unassigned. The lines are
 * straight, not roads: they show order and rough spread, not drive times.
 */
export default function PlanMap({ data, office, selectedId, onSelect, height = '100%' }: Props) {
  const points = useMemo(() => allPoints(data, office), [data, office]);
  const signature = points.map((p) => p.join(',')).join('|');
  const selectedAt = useMemo(() => {
    for (const r of data.routes) for (const s of r.stops) if (s.jobId === selectedId) return s.at;
    for (const m of data.misses) if (m.jobId === selectedId) return m.at;
    return null;
  }, [data, selectedId]);

  return (
    <div
      className="overflow-hidden rounded-xl border border-line"
      style={{ height }}
      role="region"
      aria-label="Map of the plan"
    >
      <MapContainer center={US_CENTER} zoom={4} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Fit points={points} signature={signature} />
        <Reveal at={selectedAt} />
        {office && <OfficeMarker at={office} />}
        {data.routes.map((route) => (
          <Polyline
            key={`line-${route.technicianId}`}
            positions={route.line}
            pathOptions={{ color: route.color, weight: 3, opacity: 0.85, dashArray: '8 8' }}
          />
        ))}
        {data.misses.map((m) => (
          <Marker
            key={`miss-${m.jobId}`}
            position={m.at}
            icon={missIcon(m.jobId === selectedId)}
            zIndexOffset={m.jobId === selectedId ? 1000 : 0}
            eventHandlers={{ click: () => onSelect(m.jobId) }}
          >
            <Tooltip direction="top" offset={[0, -14]}>{m.label}</Tooltip>
          </Marker>
        ))}
        {data.routes.flatMap((route) =>
          route.stops.map((s) => (
            <Marker
              key={`stop-${s.jobId}`}
              position={s.at}
              icon={numberIcon(s.number, route.color, s.jobId === selectedId)}
              zIndexOffset={s.jobId === selectedId ? 1000 : 100}
              eventHandlers={{ click: () => onSelect(s.jobId) }}
            >
              <Tooltip direction="top" offset={[0, -16]}>{s.label}</Tooltip>
            </Marker>
          )),
        )}
      </MapContainer>
    </div>
  );
}
