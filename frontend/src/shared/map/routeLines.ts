// Route lines for the dispatcher map: one line per technician and day, joining
// their planned stops in the order the server numbered them. Pure, so it is tested
// without a browser; JobsMap.tsx only turns it into Leaflet lines.
import type { MapPin } from '../api/client';
import type { Technician } from '../api/models';
import { techColor, type Point } from '../../dispatcher/plan/planMapModel';

export interface RouteLine {
  /** technician id and day, so two days of one technician are two lines. */
  key: string;
  technicianId: number;
  color: string;
  /** The office (when known), then each stop in stop order. */
  line: Point[];
}

/** Only jobs still to do are part of a route: finished and cancelled ones are history. */
const ACTIVE = new Set(['assigned', 'ongoing']);

export function buildRouteLines(
  pins: MapPin[],
  technicians: Technician[],
  office: { lat: number; lng: number } | null,
): RouteLine[] {
  const groups = new Map<string, MapPin[]>();
  for (const p of pins) {
    if (!ACTIVE.has(p.status) || p.technician_id === null || p.sequence_position === null) continue;
    const key = `${p.technician_id}|${p.scheduled_date}`;
    groups.set(key, [...(groups.get(key) ?? []), p]);
  }
  const lines: RouteLine[] = [];
  for (const [key, stops] of groups) {
    if (stops.length < 2) continue; // one stop is a pin, not a route
    stops.sort((a, b) => (a.sequence_position ?? 0) - (b.sequence_position ?? 0) || a.id - b.id);
    const technicianId = stops[0].technician_id as number;
    lines.push({
      key,
      technicianId,
      color: techColor(technicianId, technicians),
      line: [...(office ? [[office.lat, office.lng] as Point] : []), ...stops.map((s) => [s.lat, s.lng] as Point)],
    });
  }
  return lines.sort((a, b) => a.key.localeCompare(b.key));
}
