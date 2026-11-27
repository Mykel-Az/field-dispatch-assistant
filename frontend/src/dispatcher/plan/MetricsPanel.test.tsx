// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DayMetrics, PlanMetrics } from '../../shared/api/models';
import MetricsPanel from './MetricsPanel';
import { milesSaved } from './metricsModel';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ fetchScheduleMetrics: vi.fn() }));
vi.mock('../../shared/api/client', () => api);

const m = (over: Partial<PlanMetrics> = {}): PlanMetrics => ({
  jobs: 4,
  unplaced: 0,
  sla_breaches: 0,
  late_minutes: 0,
  travel_miles: 40,
  min_jobs: 2,
  max_jobs: 2,
  workload_spread: 0,
  ...over,
});
const day = (over: Partial<DayMetrics> = {}): DayMetrics => ({
  plan_date: '2026-11-27',
  jobs: 4,
  in_queue: 0,
  plan: m({ travel_miles: 25 }),
  baseline: m({
    travel_miles: 100,
    sla_breaches: 2,
    late_minutes: 45,
    workload_spread: 2,
  }),
  ...over,
});

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  api.fetchScheduleMetrics.mockReset();
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});
const mount = () =>
  act(async () => {
    root.render(<MetricsPanel date="2026-11-27" refreshKey={0} />);
  });

describe('milesSaved', () => {
  it('is the whole-number percentage of the baseline miles that the plan saves', () => {
    expect(milesSaved(m({ travel_miles: 25 }), m({ travel_miles: 100 }))).toBe(75);
    expect(milesSaved(m({ travel_miles: 30 }), m({ travel_miles: 0 }))).toBeNull();
  });
});

describe('MetricsPanel', () => {
  it('shows both columns side by side and the miles saved', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(day());
    await mount();
    expect(api.fetchScheduleMetrics).toHaveBeenCalledWith('2026-11-27');
    const rows = [...host.querySelectorAll('tbody tr')].map((r) =>
      [...r.children].map((c) => c.textContent),
    );
    expect(rows).toContainEqual(['Miles driven', '25.0', '100.0']);
    expect(rows).toContainEqual(['SLA breaches', '0', '2']);
    expect(host.textContent).toContain('The planner drives 75% fewer miles.');
  });

  it('says how many queued jobs are not counted', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(day({ in_queue: 3 }));
    await mount();
    expect(host.textContent).toContain('3 still in the queue are not counted');
  });

  it('renders nothing for a day with no placed jobs', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(day({ jobs: 0 }));
    await mount();
    expect(host.querySelector('table')).toBeNull();
  });

  it('does not claim savings when the planner drove more', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(
      day({
        plan: m({ travel_miles: 120 }),
        baseline: m({ travel_miles: 100 }),
      }),
    );
    await mount();
    expect(host.textContent).not.toContain('fewer miles');
  });

  it('says so when the comparison cannot be loaded, without breaking the page', async () => {
    api.fetchScheduleMetrics.mockRejectedValue(new Error('boom'));
    await mount();
    expect(host.textContent).toContain('Could not load the comparison.');
  });
});
