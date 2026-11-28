// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DayMetrics, PlanMetrics } from '../../shared/api/models';
import MetricsPanel from './MetricsPanel';
import { barWidths, MEASURES, winner } from './metricsModel';

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
  baseline: m({ travel_miles: 100, sla_breaches: 2, late_minutes: 45, workload_spread: 2 }),
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
const card = (title: string) =>
  [...host.querySelectorAll('li')].find((li) => li.querySelector('h3')?.textContent === title)!;

describe('winner and barWidths', () => {
  const miles = MEASURES.find((x) => x.key === 'miles')!;
  it('lower wins, and a tenth of a mile apart is a real difference but rounding noise is not', () => {
    expect(winner(miles, m({ travel_miles: 25 }), m({ travel_miles: 100 }))).toBe('planner');
    expect(winner(miles, m({ travel_miles: 120 }), m({ travel_miles: 100 }))).toBe('baseline');
    expect(winner(miles, m({ travel_miles: 10.01 }), m({ travel_miles: 10.04 }))).toBe('same');
    expect(winner(miles, m({ travel_miles: 10.0 }), m({ travel_miles: 10.1 }))).toBe('planner');
  });

  it('scales the pair against the longer bar, with a visible sliver for a small value', () => {
    expect(barWidths(25, 100)).toEqual([25, 100]);
    expect(barWidths(0, 50)).toEqual([0, 100]);
    expect(barWidths(0, 0)).toEqual([0, 0]);
    expect(barWidths(1, 1000)[0]).toBe(3);
  });
});

describe('MetricsPanel', () => {
  it('says how many measures the planner wins, and shows both values per measure', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(day());
    await mount();
    expect(api.fetchScheduleMetrics).toHaveBeenCalledWith('2026-11-27');
    expect(host.textContent).toContain('The planner is better on 4 of 4 measures.');
    const driving = card('Driving');
    expect(driving.textContent).toContain('25.0 mi');
    expect(driving.textContent).toContain('100.0 mi');
    expect(driving.textContent).toContain('Planner is better');
    expect(card('Late arrivals').textContent).toContain('2');
  });

  it('is honest when the planner drives more: the verdict says round-robin is better', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(
      day({ plan: m({ travel_miles: 120 }), baseline: m({ travel_miles: 100 }) }),
    );
    await mount();
    expect(card('Driving').textContent).toContain('Round-robin is better');
    expect(host.textContent).toContain('better on 0 of 4 measures and worse on 1');
  });

  it('says Same when the two tie, and does not give the verdict by colour alone', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(day({ plan: m(), baseline: m() }));
    await mount();
    expect(card('Uneven workload').textContent).toContain('= Same');
  });

  it('draws the longer value as the longer bar', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(day());
    await mount();
    const bars = [...card('Driving').querySelectorAll<HTMLElement>('div[style]')].map(
      (b) => b.style.width,
    );
    expect(bars).toEqual(['25%', '100%']);
  });

  it('says how many queued jobs are not counted, and flags jobs that could not be placed', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(
      day({ in_queue: 3, baseline: m({ unplaced: 2, travel_miles: 100 }) }),
    );
    await mount();
    expect(host.textContent).toContain('3 still in the queue are not counted');
    expect(host.textContent).toContain('planner 0, round-robin 2');
  });

  it('renders nothing for a day with no placed jobs', async () => {
    api.fetchScheduleMetrics.mockResolvedValue(day({ jobs: 0 }));
    await mount();
    expect(host.querySelector('ul')).toBeNull();
  });

  it('says so when the comparison cannot be loaded, without breaking the page', async () => {
    api.fetchScheduleMetrics.mockRejectedValue(new Error('boom'));
    await mount();
    expect(host.textContent).toContain('Could not load the comparison.');
  });
});
