import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect } from 'react';
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';

export interface LatLng {
  lat: number;
  lng: number;
}

// Where to look when nothing is known yet: the whole United States.
const US_CENTER: LatLng = { lat: 39.8, lng: -98.6 };

// A plain CSS pin: Leaflet's stock marker images do not survive bundling.
const pinIcon = L.divIcon({
  className: '',
  iconSize: [28, 36],
  iconAnchor: [14, 34],
  html: `<svg width="28" height="36" viewBox="0 0 18 22" aria-hidden="true">
    <path d="M9 1C4.6 1 1 4.5 1 8.8c0 5.6 8 12.2 8 12.2s8-6.6 8-12.2C17 4.5 13.4 1 9 1Z"
      fill="#0f766e" stroke="#2a2622" stroke-width="1"/><circle cx="9" cy="9" r="3.2" fill="#fff"/></svg>`,
});

function Clicks({ onPick }: { onPick: (p: LatLng) => void }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }) });
  return null;
}

function Follow({ target, zoom }: { target: LatLng; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([target.lat, target.lng], Math.max(map.getZoom(), zoom));
  }, [map, target.lat, target.lng, zoom]);
  return null;
}

interface Props {
  /** The current pin, if any. */
  pin: LatLng | null;
  /** When given, clicking the map or dragging the pin reports the new place. */
  onPick?: (p: LatLng) => void;
  /** Where to look when there is no pin yet (e.g. the office). */
  fallbackCenter?: LatLng | null;
  height?: number;
}

/** A map with one pin, which the dispatcher can click or drag to correct. */
export default function PinMap({ pin, onPick, fallbackCenter, height = 260 }: Props) {
  const start = pin ?? fallbackCenter ?? US_CENTER;
  return (
    <div
      className="overflow-hidden rounded-xl border border-line"
      style={{ height }}
      role="application"
      aria-label={onPick ? 'Map: click to place the pin' : 'Map'}
    >
      <MapContainer
        center={[start.lat, start.lng]}
        zoom={pin ? 16 : fallbackCenter ? 11 : 4}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {onPick && <Clicks onPick={onPick} />}
        {pin && (
          <>
            <Follow target={pin} zoom={15} />
            <Marker
              position={[pin.lat, pin.lng]}
              icon={pinIcon}
              draggable={Boolean(onPick)}
              eventHandlers={{
                dragend: (e) => {
                  const p = (e.target as L.Marker).getLatLng();
                  onPick?.({ lat: p.lat, lng: p.lng });
                },
              }}
            />
          </>
        )}
      </MapContainer>
    </div>
  );
}
