// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../shared/api/http';
import type { ScheduleResult } from '../../shared/api/models';
import PlanPage from './PlanPage';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({
  fetchSchedule: vi.fn(),
  generateSchedule: vi.fn(),
  fetchTechnicians: vi.fn(),
  fetchJobs: vi.fn(),
  fetchMapJobs: vi.fn(),
  fetchOrganization: vi.fn(),
  fetchScheduleMetrics: vi.fn(),
}));
vi.mock('../../shared/api/client', () => api);
// Leaflet needs a real browser; the map is checked there.
vi.mock('../plan/PlanMap', () => ({ default: () => null }));
vi.mock('../../auth/useAuth', () => ({
  useAuth: () => ({
    user: { organization: { timezone: 'America/Chicago' }, role: 'dispatcher' },
  }),
}));

const nothing: ScheduleResult = { plan_date: '2026-11-02', assigned: [], unassigned: [], skipped: [] };

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  api.fetchSchedule.mockReset().mockResolvedValue(nothing);
  api.generateSchedule.mockReset();
  api.fetchTechnicians.mockReset().mockResolvedValue([]);
  api.fetchJobs.mockReset().mockResolvedValue({ results: [], next: null });
  api.fetchMapJobs.mockReset().mockResolvedValue({ results: [], truncated: false });
  api.fetchScheduleMetrics.mockReset().mockRejectedValue(new Error('not in this test'));
  api.fetchOrganization.mockReset().mockResolvedValue({ lat: 30, lng: -97 });
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
    root.render(
      <MemoryRouter>
        <PlanPage />
      </MemoryRouter>,
    );
  });

const buttons = () => [...host.querySelectorAll('button')].map((b) => b.textContent);

const click = async (label: string) => {
  const button = [...host.querySelectorAll('button')].find((b) => b.textContent?.includes(label));
  expect(button, `button "${label}"`).toBeTruthy();
  await act(async () => {
    button!.click();
  });
};

const done: ScheduleResult = {
  plan_date: '2026-11-02',
  assigned: [
    {
      job_id: 10,
      placed_by: 'planner',
      technician_id: 1,
      estimated_arrival: '2026-11-02T15:12:00Z',
      sla_label: 'ok',
      slack_minutes: 20,
      reasons: [],
      sentence: 'Sam was chosen.',
    },
  ],
  unassigned: [],
  skipped: [],
};

describe('PlanPage', () => {
  it('starts with a day picker and a Run plan button, and says nothing is planned yet', async () => {
    await mount();
    expect(host.querySelector('input[type="date"]')).toBeTruthy();
    expect(host.textContent).toContain('Run plan');
    expect(host.textContent).toContain('Nothing planned for');
    expect(host.querySelector('[role="status"]')).toBeNull();
  });

  it('shows the plan that is already saved, without running anything', async () => {
    api.fetchSchedule.mockResolvedValue(done);
    await mount();
    expect(host.textContent).toContain('Planned 1 job across 1 technician');
    expect(host.textContent).toContain('Sam was chosen.');
    expect(api.generateSchedule).not.toHaveBeenCalled();
  });

  it('asks for the day that was picked, and again when it changes', async () => {
    await mount();
    const first = api.fetchSchedule.mock.calls[0][0];
    expect(first).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    const input = host.querySelector('input[type="date"]') as HTMLInputElement;
    const next = new Date(`${first}T12:00:00Z`);
    next.setUTCDate(next.getUTCDate() + 1);
    const nextDay = next.toISOString().slice(0, 10);
    await act(async () => {
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
      set.call(input, nextDay);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    expect(api.fetchSchedule).toHaveBeenLastCalledWith(nextDay);
  });

  it('is one button: Run plan until the planner has placed jobs, then Plan again (replan)', async () => {
    api.generateSchedule.mockResolvedValue(done);
    api.fetchSchedule.mockResolvedValueOnce(nothing).mockResolvedValue(done);
    await mount();
    expect(buttons()).not.toContain('Plan again');
    await click('Run plan');
    expect(api.generateSchedule).toHaveBeenLastCalledWith(expect.stringMatching(/^\d{4}-/), false);
    expect(buttons()).not.toContain('Run plan');
    await click('Plan again');
    expect(api.generateSchedule).toHaveBeenLastCalledWith(expect.stringMatching(/^\d{4}-/), true);
    expect(api.generateSchedule).toHaveBeenCalledTimes(2);
  });

  it('stays "Run plan" when everything on the day was assigned by hand', async () => {
    api.fetchSchedule.mockResolvedValue({
      ...done,
      assigned: [{ ...done.assigned[0], placed_by: 'manual' }],
    });
    await mount();
    expect(buttons()).toContain('Run plan');
    expect(buttons()).not.toContain('Plan again');
  });

  it('shows a job assigned by hand with its technician, not only what a run just placed', async () => {
    api.fetchSchedule.mockResolvedValue({
      ...done,
      assigned: [
        ...done.assigned,
        {
          job_id: 11,
          technician_id: 1,
          estimated_arrival: null,
          sla_label: 'unknown',
          slack_minutes: 0,
          reasons: [],
          sentence: '',
          placed_by: 'manual',
        },
      ],
    });
    await mount();
    expect(host.textContent).toContain('Planned 2 jobs across 1 technician');
    expect(host.textContent).toContain('Assigned by hand');
  });

  it('says it is loading, then clears that message', async () => {
    let finish: (r: ScheduleResult) => void = () => {};
    api.fetchSchedule.mockReturnValue(new Promise<ScheduleResult>((r) => (finish = r)));
    await mount();
    expect(host.textContent).toContain('Loading the plan');
    await act(async () => finish(nothing));
    expect(host.textContent).not.toContain('Loading the plan');
  });

  it('offers a retry when the saved plan cannot be loaded', async () => {
    api.fetchSchedule.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await mount();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('load the plan');
    api.fetchSchedule.mockResolvedValueOnce(done);
    await click('Try again');
    expect(host.querySelector('[role="alert"]')).toBeNull();
    expect(host.textContent).toContain('Planned 1 job');
  });

  it('runs the plan for the chosen day and shows the results', async () => {
    api.generateSchedule.mockResolvedValue(done);
    api.fetchSchedule.mockResolvedValueOnce(nothing).mockResolvedValue(done);
    await mount();
    await click('Run plan');
    expect(api.generateSchedule).toHaveBeenCalledTimes(1);
    expect(api.generateSchedule.mock.calls[0][0]).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(host.textContent).toContain('Planned 1 job across 1 technician');
    expect(host.textContent).toContain('Sam was chosen.');
  });

  it('disables the button while planning, so a double click cannot plan twice', async () => {
    let finish: (r: ScheduleResult) => void = () => {};
    api.generateSchedule.mockReturnValue(new Promise<ScheduleResult>((r) => (finish = r)));
    await mount();
    await click('Run plan');
    const button = [...host.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Planning'),
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    await act(async () => finish(done));
    expect(api.generateSchedule).toHaveBeenCalledTimes(1);
  });

  it('shows the whole day after a run, not only the jobs that run looked at', async () => {
    // A second run on a planned day has nothing new to place; the page must still list the day's plan.
    api.generateSchedule.mockResolvedValue(nothing);
    api.fetchSchedule.mockResolvedValue(done);
    await mount();
    await click('Plan again');
    expect(host.textContent).toContain('Sam was chosen.');
  });

  it('falls back to what the run returned when the day cannot be reloaded', async () => {
    api.generateSchedule.mockResolvedValue(done);
    api.fetchSchedule.mockResolvedValueOnce(nothing).mockRejectedValue(new Error('down'));
    await mount();
    await click('Run plan');
    expect(host.textContent).toContain('Sam was chosen.');
    expect(host.querySelector('[role=alert]')).toBeNull();
  });

  it('sends a 409 to the organization settings', async () => {
    api.generateSchedule.mockRejectedValue(
      new ApiError(409, { detail: 'Set the organization’s location and working hours before planning.' }),
    );
    await mount();
    await click('Run plan');
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('before planning');
    expect(host.querySelector('a[href="/organization"]')).toBeTruthy();
  });

  it('explains a 403 without offering a retry', async () => {
    api.generateSchedule.mockRejectedValue(new ApiError(403, { detail: 'nope' }));
    await mount();
    await click('Run plan');
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('Only dispatchers');
    expect([...host.querySelectorAll('button')].some((b) => b.textContent === 'Try again')).toBe(false);
  });

  it('shows the server’s message for a rejected day', async () => {
    api.generateSchedule.mockRejectedValue(
      new ApiError(400, { date: ['Cannot plan a day that has passed.'] }),
    );
    await mount();
    await click('Run plan');
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('has passed');
  });

  it('offers a retry after a network failure, and a retry works', async () => {
    api.generateSchedule.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    api.fetchSchedule.mockResolvedValueOnce(nothing).mockResolvedValue(done);
    await mount();
    await click('Run plan');
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('try again');
    api.generateSchedule.mockResolvedValueOnce(done);
    await click('Try again');
    expect(host.querySelector('[role="alert"]')).toBeNull();
    expect(host.textContent).toContain('Planned 1 job');
  });

  it('still shows the plan when the technician or job lookups fail', async () => {
    api.generateSchedule.mockResolvedValue(done);
    api.fetchSchedule.mockResolvedValueOnce(nothing).mockResolvedValue(done);
    api.fetchTechnicians.mockRejectedValue(new Error('x'));
    api.fetchJobs.mockRejectedValue(new Error('x'));
    await mount();
    await click('Run plan');
    expect(host.textContent).toContain('Technician #1');
    expect(host.textContent).toContain('Job #10');
  });

  it('asks where the day’s jobs are, for the map', async () => {
    api.fetchSchedule.mockResolvedValue(done);
    await mount();
    expect(api.fetchMapJobs).toHaveBeenCalledWith(
      expect.objectContaining({ date: '2026-11-02', statuses: ['assigned', 'ongoing', 'unassigned'] }),
    );
  });

  it('still shows the plan when the locations cannot be loaded', async () => {
    api.fetchSchedule.mockResolvedValue(done);
    api.fetchMapJobs.mockRejectedValue(new Error('down'));
    await mount();
    expect(host.textContent).toContain('Sam was chosen.');
    expect(host.querySelector('[role=alert]')).toBeNull();
  });
});
