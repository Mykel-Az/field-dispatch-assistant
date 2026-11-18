// What the plan map draws, worked out from the plan and the job locations. Pure,
// so it is tested without a browser; PlanMap.tsx only turns this into Leaflet.
import type { PlannedJob, Technician, UnplannedJob } from '../../shared/api/models';
import type { TechnicianPlan } from './planModel';

export type Point = [lat: number, lng: number];

/**
 * One colour per technician, dark enough for white numbers on it. The number on
 * each marker (not the colour) says which stop it is, so the map still reads for
 * someone who cannot tell the colours apart.
 */
export const TECH_COLORS = [
  '#0f766e', '#1d4ed8', '#7c3aed', '#be123c', '#b45309', '#4d7c0f', '#a21caf', '#475569',
];

/**
 * Stable for a technician across days: by their place in the list ordered by id,
 * not by who happens to be in today's plan, so Sam stays teal all week.
 */
export function techColor(technicianId: number, technicians: Technician[]): string {
  const ids = technicians.map((t) => t.id).sort((a, b) => a - b);
  const at = ids.indexOf(technicianId);
  return TECH_COLORS[(at === -1 ? technicianId : at) % TECH_COLORS.length];
}

export interface MapStop {
  jobId: number;
  /** 1-based, in the order the technician drives. Matches the number on the card. */
  number: number;
  at: Point;
  label: string;
}
export interface MapRoute {
  technicianId: number;
  name: string;
  color: string;
  /** Office (when known) then each stop in visit order: what the line joins. */
  line: Point[];
  stops: MapStop[];
}
export interface MapMiss {
  jobId: number;
  at: Point;
  label: string;
}
export interface PlanMapData {
  routes: MapRoute[];
  /** Jobs the planner could not place, shown so the gaps are visible. */
  misses: MapMiss[];
  /** Planned stops with no known location: drawn nowhere, reported in words. */
  unplaced: number;
}

interface Input {
  plans: TechnicianPlan[];
  unassigned: UnplannedJob[];
  /** Job id to where it is, from the map endpoint. */
  locations: Map<number, { lat: number; lng: number }>;
  technicians: Technician[];
  office: { lat: number; lng: number } | null;
  titleOf: (jobId: number) => string;
  timeOf: (stop: PlannedJob) => string;
}

export function buildPlanMap(input: Input): PlanMapData {
  const { plans, unassigned, locations, technicians, office, titleOf, timeOf } = input;
  let unplaced = 0;
  const routes: MapRoute[] = [];
  for (const plan of plans) {
    const stops: MapStop[] = [];
    plan.stops.forEach((stop, i) => {
      const where = locations.get(stop.job_id);
      if (!where) {
        unplaced += 1;
        return;
      }
      stops.push({
        jobId: stop.job_id,
        number: i + 1,
        at: [where.lat, where.lng],
        label: `${i + 1} · ${timeOf(stop)} · ${titleOf(stop.job_id)}`,
      });
    });
    if (stops.length === 0) continue;
    routes.push({
      technicianId: plan.technicianId,
      name: plan.name,
      color: techColor(plan.technicianId, technicians),
      line: [...(office ? [[office.lat, office.lng] as Point] : []), ...stops.map((s) => s.at)],
      stops,
    });
  }
  const misses: MapMiss[] = [];
  for (const job of unassigned) {
    const where = locations.get(job.job_id);
    if (where) misses.push({ jobId: job.job_id, at: [where.lat, where.lng], label: `Not assigned · ${titleOf(job.job_id)}` });
  }
  return { routes, misses, unplaced };
}

/** Every point the map should fit into view. */
export function allPoints(data: PlanMapData, office: { lat: number; lng: number } | null): Point[] {
  const points = [...data.routes.flatMap((r) => r.stops.map((s) => s.at)), ...data.misses.map((m) => m.at)];
  if (office) points.push([office.lat, office.lng]);
  return points;
}
