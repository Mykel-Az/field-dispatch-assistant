// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { JobRow, ScheduleResult, Technician } from '../../shared/api/models';
import PlanResults from './PlanResults';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// Leaflet needs a real browser. The stand-in has one button per marker and shows which is selected.
vi.mock('./PlanMap', () => ({
  default: ({ data, selectedId, onSelect }: {
    data: { routes: { stops: { jobId: number; number: number }[] }[]; misses: { jobId: number }[] };
    selectedId: number | null;
    onSelect: (id: number) => void;
  }) => (
    <div data-testid="map" data-selected={String(selectedId)}>
      {data.routes.flatMap((r) => r.stops).map((s) => (
        <button key={s.jobId} data-marker={s.jobId} onClick={() => onSelect(s.jobId)}>pin {s.number}</button>
      ))}
      {data.misses.map((m) => (
        <button key={m.jobId} data-marker={m.jobId} onClick={() => onSelect(m.jobId)}>miss</button>
      ))}
    </div>
  ),
}));

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

describe('PlanResults map', () => {
  const planned: ScheduleResult = {
    ...base,
    assigned: [10, 11].map((id, i) => ({
      job_id: id, technician_id: 1, estimated_arrival: `2026-11-02T1${5 + i}:00:00Z`,
      sla_label: 'ok', slack_minutes: 30, reasons: [], sentence: `Sam for ${id}.`,
    })),
    unassigned: [{ job_id: 12, reasons: [], sentence: 'No one could take it.' }],
  } as unknown as ScheduleResult;
  const where = new Map([[10, { lat: 30.1, lng: -97.1 }], [11, { lat: 30.2, lng: -97.2 }], [12, { lat: 30.3, lng: -97.3 }]]);
  const mountMap = (locations?: typeof where) =>
    act(() =>
      root.render(
        <MemoryRouter>
          <PlanResults result={planned} technicians={technicians} jobs={jobs} timezone="America/Chicago"
            locations={locations} office={{ lat: 30, lng: -97 }} />
        </MemoryRouter>,
      ),
    );
  const card = (id: number) => host.querySelector(`#plan-job-${id}`) as HTMLElement;
  const click = (el: Element) => act(() => (el as HTMLElement).click());

  it('shows the map, its key, and a numbered badge on each stop', async () => {
    await mountMap(where);
    expect(host.querySelector('[data-testid=map]')).toBeTruthy();
    expect(host.textContent).toContain('not road routes');
    expect(card(10).querySelector('[aria-label="Stop 1"]')).toBeTruthy();
    expect(card(11).querySelector('[aria-label="Stop 2"]')).toBeTruthy();
  });

  it('has no map when no job has a known location', async () => {
    await mountMap(undefined);
    expect(host.querySelector('[data-testid=map]')).toBeNull();
    expect(host.textContent).toContain('Sam for 10.'); // the plan itself is unaffected
  });

  it('lights up a card when its marker is clicked, and clears the previous one', async () => {
    await mountMap(where);
    await click(host.querySelector('[data-marker="10"]')!);
    expect(card(10).className).toContain('ring-2');
    await click(host.querySelector('[data-marker="11"]')!);
    expect(card(11).className).toContain('ring-2');
    expect(card(10).className).not.toContain('ring-2');
  });

  it('lights up the marker when its card is clicked, unassigned jobs included', async () => {
    await mountMap(where);
    await click(card(11));
    expect(host.querySelector('[data-testid=map]')!.getAttribute('data-selected')).toBe('11');
    await click(card(12));
    expect(host.querySelector('[data-testid=map]')!.getAttribute('data-selected')).toBe('12');
    expect(card(12).className).toContain('ring-2');
  });
});

