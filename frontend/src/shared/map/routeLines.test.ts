import { describe, expect, it } from 'vitest';
import type { MapPin } from '../api/client';
import type { Technician } from '../api/models';
import { TECH_COLORS } from '../../dispatcher/plan/planMapModel';
import { buildRouteLines } from './routeLines';

const tech = (id: number) => ({ id }) as unknown as Technician;
const pin = (id: number, over: Partial<MapPin> = {}): MapPin =>
  ({
    id,
    lat: 30 + id / 100,
    lng: -97,
    status: 'assigned',
    technician_id: 1,
    is_urgent: false,
    scheduled_date: '2026-11-25',
    sequence_position: id,
    ...over,
  }) as MapPin;
const OFFICE = { lat: 30, lng: -97 };

describe('buildRouteLines', () => {
  it('joins one technician’s stops in stop order, from the office', () => {
    const [route] = buildRouteLines([pin(3), pin(1), pin(2)], [tech(1)], OFFICE);
    expect(route.line).toEqual([[30, -97], [30.01, -97], [30.02, -97], [30.03, -97]]);
    expect(route.color).toBe(TECH_COLORS[0]);
  });

  it('draws no line for a single stop, an unassigned job, or a finished one', () => {
    expect(buildRouteLines([pin(1)], [tech(1)], OFFICE)).toEqual([]);
    expect(
      buildRouteLines([pin(1, { status: 'unassigned', technician_id: null }), pin(2, { status: 'unassigned', technician_id: null })], [], OFFICE),
    ).toEqual([]);
    expect(buildRouteLines([pin(1, { status: 'completed' }), pin(2)], [tech(1)], OFFICE)).toEqual([]);
  });

  it('keeps technicians and days apart', () => {
    const pins = [
      pin(1), pin(2),
      pin(3, { technician_id: 2, sequence_position: 1 }),
      pin(4, { technician_id: 2, sequence_position: 2 }),
      pin(5, { scheduled_date: '2026-11-26', sequence_position: 1 }),
      pin(6, { scheduled_date: '2026-11-26', sequence_position: 2 }),
    ];
    const routes = buildRouteLines(pins, [tech(1), tech(2)], null);
    expect(routes.map((r) => r.key)).toEqual(['1|2026-11-25', '1|2026-11-26', '2|2026-11-25']);
    expect(routes[0].line).toHaveLength(2); // no office: just the stops
    expect(routes[2].color).toBe(TECH_COLORS[1]);
  });

  it('ignores a pin with no stop number', () => {
    expect(buildRouteLines([pin(1, { sequence_position: null }), pin(2)], [tech(1)], OFFICE)).toEqual([]);
  });
});
