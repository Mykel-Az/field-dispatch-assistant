// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it } from 'vitest';
import PlanMapKey from './PlanMapKey';
import type { PlanMapData } from './planMapModel';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const data = (over: Partial<PlanMapData> = {}): PlanMapData => ({
  routes: [{ technicianId: 1, name: 'Aisha Bello', color: '#0f766e', line: [], stops: [] }],
  misses: [],
  unplaced: 0,
  ...over,
});
function text(d: PlanMapData, hasOffice = true) {
  const host = document.createElement('div');
  act(() => createRoot(host).render(<PlanMapKey data={d} hasOffice={hasOffice} />));
  return host.textContent ?? '';
}

describe('PlanMapKey', () => {
  it('names each technician and says the lines are not roads', () => {
    const t = text(data());
    expect(t).toContain('Aisha Bello');
    expect(t).toContain('straight lines, not road routes');
    expect(t).toContain('starting at the office');
  });
  it('lists unassigned only when there are some', () => {
    expect(text(data())).not.toContain('Not assigned');
    expect(text(data({ misses: [{ jobId: 1, at: [1, 1], label: 'x' }] }))).toContain('Not assigned');
  });
  it('does not mention the office when it is unknown', () => {
    const t = text(data(), false);
    expect(t).not.toContain('Office');
    expect(t).not.toContain('starting at the office');
  });
  it('reports stops that could not be drawn', () => {
    expect(text(data({ unplaced: 1 }))).toContain('1 planned stop is not on the map');
    expect(text(data({ unplaced: 3 }))).toContain('3 planned stops are not on the map');
  });
});
