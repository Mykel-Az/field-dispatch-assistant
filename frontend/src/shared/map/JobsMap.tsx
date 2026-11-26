import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet';
import type { MapPin } from '../api/client';
import StatusPin from '../components/StatusPin';
import { isJobStatus } from '../status';
import OfficeMarker from './OfficeMarker';
import type { RouteLine } from './routeLines';
import type { LatLng } from './PinMap';

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
function FitToPins({ pins, office }: { pins: MapPin[]; office: LatLng | null }) {
  const map = useMap();
  const key = `${pins.map((p) => p.id).join(',')}|${office ? `${office.lat},${office.lng}` : ''}`;
  useEffect(() => {
    const points = pins.map((p) => [p.lat, p.lng] as [number, number]);
    if (office) points.push([office.lat, office.lng]); // the base is always in view
    if (points.length === 0) return;
    map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15 });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refit only when the ids or office change
  }, [map, key]);
  return null;
}

interface Props {
  pins: MapPin[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  /** The office, drawn on the map and included when fitting the view. */
  office?: LatLng | null;
  /** One dashed line per technician and day, in stop order (straight lines, not roads). */
  routes?: RouteLine[];
  height?: number | string;
}

export default function JobsMap({ pins, selectedId, onSelect, office = null, routes = [], height = 520 }: Props) {
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
        <FitToPins pins={pins} office={office} />
        {office && <OfficeMarker at={office} />}
        {routes.map((r) => (
          <Polyline
            key={r.key}
            positions={r.line}
            pathOptions={{ color: r.color, weight: 3, opacity: 0.85, dashArray: '8 8' }}
          />
        ))}
        {ordered.map((p) => (
          <Marker
            key={p.id}
            position={[p.lat, p.lng]}
            icon={iconFor(p.status, p.id === selectedId)}
            eventHandlers={{ click: () => onSelect(p.id) }}
          >
            {p.sequence_position !== null && p.technician_id !== null && (p.status === 'assigned' || p.status === 'ongoing') && (
              <Tooltip direction="top" offset={[0, -26]}>Stop {p.sequence_position}</Tooltip>
            )}
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
