import { describe, expect, it } from 'vitest';
import type { PlannedJob, Technician, UnplannedJob } from '../../shared/api/models';
import { allPoints, buildPlanMap, TECH_COLORS, techColor } from './planMapModel';
import type { TechnicianPlan } from './planModel';

const tech = (id: number) => ({ id }) as unknown as Technician;
const stop = (job_id: number, technician_id: number) => ({ job_id, technician_id }) as unknown as PlannedJob;
const plan = (technicianId: number, name: string, stops: PlannedJob[]): TechnicianPlan => ({
  technicianId, name, shift: '', stops,
});
const miss = (job_id: number) => ({ job_id }) as unknown as UnplannedJob;
const where = (entries: [number, number, number][]) =>
  new Map(entries.map(([id, lat, lng]) => [id, { lat, lng }]));
const OFFICE = { lat: 30, lng: -97 };

const base = {
  technicians: [tech(7), tech(3), tech(9)],
  office: OFFICE,
  titleOf: (id: number) => `Job ${id}`,
  timeOf: () => '09:00',
};

describe('techColor', () => {
  it('is stable by place in the technician list, whoever is in the plan', () => {
    const all = [tech(7), tech(3), tech(9)];
    expect(techColor(3, all)).toBe(TECH_COLORS[0]);
    expect(techColor(7, all)).toBe(TECH_COLORS[1]);
    expect(techColor(9, all)).toBe(TECH_COLORS[2]);
  });
  it('wraps when there are more technicians than colours', () => {
    const many = Array.from({ length: 10 }, (_, i) => tech(i + 1));
    expect(techColor(9, many)).toBe(TECH_COLORS[0]);
  });
  it('still gives an unlisted technician a colour', () => {
    expect(TECH_COLORS).toContain(techColor(42, []));
  });
});

describe('buildPlanMap', () => {
  it('numbers each technician’s stops in driving order and joins them from the office', () => {
    const data = buildPlanMap({
      ...base,
      plans: [plan(3, 'Aisha', [stop(10, 3), stop(11, 3)])],
      unassigned: [],
      locations: where([[10, 30.1, -97.1], [11, 30.2, -97.2]]),
    });
    const [route] = data.routes;
    expect(route.stops.map((s) => [s.jobId, s.number])).toEqual([[10, 1], [11, 2]]);
    expect(route.line).toEqual([[30, -97], [30.1, -97.1], [30.2, -97.2]]);
    expect(route.stops[0].label).toBe('1 · 09:00 · Job 10');
    expect(route.color).toBe(TECH_COLORS[0]);
  });

  it('starts the line at the first stop when the office is unknown', () => {
    const data = buildPlanMap({
      ...base, office: null,
      plans: [plan(3, 'Aisha', [stop(10, 3)])], unassigned: [],
      locations: where([[10, 30.1, -97.1]]),
    });
    expect(data.routes[0].line).toEqual([[30.1, -97.1]]);
  });

  it('keeps the card number when an earlier stop has no location', () => {
    const data = buildPlanMap({
      ...base,
      plans: [plan(3, 'Aisha', [stop(10, 3), stop(11, 3)])], unassigned: [],
      locations: where([[11, 30.2, -97.2]]),
    });
    expect(data.routes[0].stops.map((s) => s.number)).toEqual([2]); // the card says 2, so the pin says 2
    expect(data.unplaced).toBe(1);
  });

  it('draws no route for a technician with nothing locatable', () => {
    const data = buildPlanMap({
      ...base, plans: [plan(3, 'Aisha', [stop(10, 3)])], unassigned: [], locations: new Map(),
    });
    expect(data.routes).toEqual([]);
    expect(data.unplaced).toBe(1);
  });

  it('shows unassigned jobs that have a location, and skips those that do not', () => {
    const data = buildPlanMap({
      ...base, plans: [], unassigned: [miss(20), miss(21)], locations: where([[20, 30.3, -97.3]]),
    });
    expect(data.misses).toEqual([{ jobId: 20, at: [30.3, -97.3], label: 'Not assigned · Job 20' }]);
  });
});

describe('allPoints', () => {
  it('covers stops, unassigned jobs and the office', () => {
    const data = buildPlanMap({
      ...base,
      plans: [plan(3, 'Aisha', [stop(10, 3)])], unassigned: [miss(20)],
      locations: where([[10, 30.1, -97.1], [20, 30.3, -97.3]]),
    });
    expect(allPoints(data, OFFICE)).toEqual([[30.1, -97.1], [30.3, -97.3], [30, -97]]);
    expect(allPoints(data, null)).toHaveLength(2);
  });
});
