// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { JobDetail, Technician } from '../../shared/api/models';
import AssignPanel from './AssignPanel';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({
  assignJob: vi.fn(),
  unassignJob: vi.fn(),
  fetchTechnicians: vi.fn(),
  fetchOrganization: vi.fn(),
  fetchMapJobs: vi.fn(),
}));
vi.mock('../../shared/api/client', () => api);

const tech = (id: number, name: string) =>
  ({ id, user: { full_name: name, is_active: true }, skills: [{ id: 1, name: 'HVAC' }] }) as unknown as Technician;
const job = (over: Partial<JobDetail> = {}) =>
  ({
    id: 5, version: 2, status: 'unassigned', is_urgent: false, geocode_status: 'ok',
    scheduled_date: '2026-11-17', slot_start: '2026-11-17T15:00:00Z',
    acceptable_skills: [{ id: 1, name: 'HVAC' }], technician: null, ...over,
  }) as unknown as JobDetail;
const pin = (id: number, technician_id: number) => ({
  id, lat: 1, lng: 1, status: 'assigned', technician_id, is_urgent: false,
});

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  api.fetchTechnicians.mockReset().mockResolvedValue([tech(1, 'Sam'), tech(2, 'Ana')]);
  api.fetchOrganization.mockReset().mockResolvedValue({ max_jobs_per_tech_per_day: 2 });
  api.fetchMapJobs.mockReset().mockResolvedValue({
    results: [pin(10, 1), pin(11, 1), pin(12, 2)],
    truncated: false,
  });
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

const mount = (j: JobDetail) =>
  act(async () => root.render(<AssignPanel job={j} onChanged={() => undefined} />));
const choose = async (name: string) => {
  const radio = [...host.querySelectorAll('[role=radio]')].find((r) => r.textContent?.includes(name));
  expect(radio, name).toBeTruthy();
  await act(async () => (radio as HTMLElement).click());
};

describe('AssignPanel daily limit hints', () => {
  it('asks for the load on the job’s own day', async () => {
    await mount(job());
    expect(api.fetchMapJobs).toHaveBeenCalledWith(
      expect.objectContaining({ date: '2026-11-17', statuses: ['assigned', 'ongoing'] }),
    );
  });

  it('shows each technician’s load', async () => {
    await mount(job());
    expect(host.textContent).toContain('2 jobs that day (limit 2)');
    expect(host.textContent).toContain('1 job that day (limit 2)');
  });

  it('warns, without blocking, when the picked technician is at the limit', async () => {
    await mount(job());
    await choose('Sam');
    expect(host.querySelector('[role=status]')?.textContent).toContain('Sam already has 2 jobs that day (limit 2)');
    const assign = [...host.querySelectorAll('button')].find((b) => b.textContent?.startsWith('Assign to'));
    expect(assign?.disabled).toBe(false);
  });

  it('does not warn for a technician under the limit', async () => {
    await mount(job());
    await choose('Ana');
    expect(host.querySelector('[role=status]')).toBeNull();
  });

  it('notes that an urgent job may go over', async () => {
    await mount(job({ is_urgent: true }));
    await choose('Sam');
    expect(host.querySelector('[role=status]')?.textContent).toContain('urgent');
  });

  it('shows no counts, and still lets you assign, when the load cannot be loaded', async () => {
    api.fetchMapJobs.mockRejectedValue(new Error('down'));
    await mount(job());
    await choose('Sam');
    expect(host.textContent).not.toContain('that day');
    expect(host.querySelector('[role=status]')).toBeNull();
  });

  it('shows no counts when the map answer was cut short', async () => {
    api.fetchMapJobs.mockResolvedValue({ results: [pin(10, 1)], truncated: true });
    await mount(job());
    expect(host.textContent).not.toContain('that day');
  });
});
