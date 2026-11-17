import L from 'leaflet';
import { Marker, Tooltip } from 'react-leaflet';
import type { LatLng } from './PinMap';

// The office / workstation: a dark square with a house outline, so it is never
// mistaken for a job pin (those are teardrops coloured by status).
const officeIcon = L.divIcon({
  className: '',
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  html: `<div style="width:32px;height:32px;border-radius:8px;background:#2a2622;border:2px solid #fff;
    box-shadow:0 1px 4px rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M3 11 12 3l9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/></svg></div>`,
});

/** The office, on any map. Not clickable, and always under the job pins. */
export default function OfficeMarker({ at }: { at: LatLng }) {
  return (
    <Marker
      position={[at.lat, at.lng]}
      icon={officeIcon}
      interactive
      keyboard={false}
      zIndexOffset={-1000}
      title="Office"
    >
      <Tooltip direction="top" offset={[0, -14]}>
        Office
      </Tooltip>
    </Marker>
  );
}
