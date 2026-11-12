// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { JobRow, ScheduleResult, Technician } from '../../shared/api/models';
import PlanResults from './PlanResults';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

const tech = (id: number, name: string): Technician =>
  ({
    id,
    user: { id: id + 100, full_name: name },
    skills: [],
    shift_start: '08:00:00',
    shift_end: '17:00:00',
    phone: null,
  }) as unknown as Technician;

const job = (id: number, title: string) => ({ id, title }) as unknown as JobRow;
const technicians = [tech(1, 'Sam'), tech(2, 'Alex')];
const jobs = new Map([
  [10, job(10, 'AC not cooling')],
  [11, job(11, 'Water heater')],
  [12, job(12, 'Furnace tune-up')],
  [13, job(13, 'Dishwasher')],
]);

const base: ScheduleResult = {
  plan_date: '2026-11-02',
  assigned: [],
  unassigned: [],
  skipped: [],
};

const mount = (result: ScheduleResult) =>
  act(() =>
    root.render(
      <MemoryRouter>
        <PlanResults
          result={result}
          technicians={technicians}
          jobs={jobs}
          timezone="America/Chicago"
        />
      </MemoryRouter>,
    ),
  );

describe('PlanResults', () => {
  it('shows an empty day plainly, with a way to the jobs', () => {
    mount(base);
    expect(host.textContent).toContain('Nothing to plan for this day');
    expect(host.querySelector('a')?.getAttribute('href')).toBe('/jobs?scheduled_date=2026-11-02');
  });

  it('groups stops under each technician with time, title, SLA and the sentence', () => {
    mount({
      ...base,
      assigned: [
        {
          job_id: 10,
          technician_id: 1,
          estimated_arrival: '2026-11-02T15:12:00Z',
          sla_label: 'ok',
          slack_minutes: 48.4,
          reasons: [
            { code: 'assigned', facts: { technician_id: 1 } },
            { code: 'unavailable', facts: { technician_id: 2 } },
          ],
          sentence: 'Sam was chosen for “AC not cooling”: 12 min away.',
        },
        {
          job_id: 11,
          technician_id: 2,
          estimated_arrival: '2026-11-02T16:00:00Z',
          sla_label: 'breach',
          slack_minutes: -6.5,
          reasons: [{ code: 'assigned', facts: { technician_id: 2 } }],
          sentence: 'Alex was chosen for “Water heater”.',
        },
      ],
    });
    const text = host.textContent ?? '';
    expect(text).toContain('Planned 2 jobs across 2 technicians');
    const sections = [...host.querySelectorAll('section')];
    expect(sections.map((s) => s.getAttribute('aria-label'))).toEqual(['Alex', 'Sam']);
    const sam = sections[1].textContent ?? '';
    expect(sam).toContain('09:12');
    expect(sam).toContain('AC not cooling');
    expect(sam).toContain('On time · 48 min to spare');
    expect(sam).toContain('Sam was chosen for “AC not cooling”: 12 min away.');
    expect(sam).toContain('Alex is unavailable');
    expect(sections[0].textContent).toContain('Late · 7 min late');
  });

  it('shows no SLA badge for a plan saved before the SLA was stored with it', () => {
    mount({
      ...base,
      assigned: [
        {
          job_id: 10,
          technician_id: 1,
          estimated_arrival: '2026-11-02T15:12:00Z',
          sla_label: 'unknown',
          slack_minutes: 0,
          reasons: [],
          sentence: 'Sam was chosen.',
        },
      ],
    });
    expect(host.textContent).toContain('09:12');
    expect(host.textContent).not.toContain('min to spare');
    expect(host.textContent).not.toContain('unknown');
  });

  it('links every job to its page', () => {
    mount({
      ...base,
      assigned: [
        {
          job_id: 10,
          technician_id: 1,
          estimated_arrival: '2026-11-02T15:12:00Z',
          sla_label: 'ok',
          slack_minutes: 10,
          reasons: [],
          sentence: '',
        },
      ],
    });
    expect(host.querySelector('a[href="/jobs/10"]')?.textContent).toBe('AC not cooling');
  });

  it('lists unassigned jobs with their reasons and a link to assign by hand', () => {
    mount({
      ...base,
      unassigned: [
        {
          job_id: 12,
          reasons: [
            { code: 'no_feasible_technician', facts: { job_id: 12, technicians_checked: 2 } },
            { code: 'skill_mismatch', facts: { technician_id: 1 } },
            { code: 'daily_limit', facts: { technician_id: 2, limit: 3 } },
          ],
          sentence: 'No technician can take “Furnace tune-up”.',
        },
      ],
    });
    const section = host.querySelector('section[aria-label="Could not be assigned"]');
    const text = section?.textContent ?? '';
    expect(text).toContain('Furnace tune-up');
    expect(text).toContain('No technician can take “Furnace tune-up”.');
    expect(text).toContain('Sam does not have a matching skill');
    expect(text).toContain('Alex has reached the daily limit of 3 jobs');
    const links = [...(section?.querySelectorAll('a') ?? [])];
    expect(links.map((a) => a.textContent)).toContain('Assign by hand');
    expect(links.every((a) => a.getAttribute('href') === '/jobs/12')).toBe(true);
    expect(host.textContent).toContain('1 job could not be assigned');
  });

  it('lists jobs that need a location', () => {
    mount({
      ...base,
      skipped: [{ job_id: 13, code: 'needs_location', sentence: '“Dishwasher” has no usable location yet.' }],
    });
    const section = host.querySelector('section[aria-label="Need a location"]');
    expect(section?.textContent).toContain('Dishwasher');
    expect(section?.textContent).toContain('Fix the location');
  });

  it('falls back to the job number when the title is not known', () => {
    mount({
      ...base,
      skipped: [{ job_id: 99, code: 'needs_location', sentence: 'x' }],
    });
    expect(host.textContent).toContain('Job #99');
  });
});