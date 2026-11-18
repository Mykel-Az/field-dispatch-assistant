// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../shared/api/http';
import type { TechnicianJob } from '../../shared/api/models';
import { initOrgTimezone } from '../../shared/jobTime';
import TechnicianHome from './TechnicianHome';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({
  fetchMyJobs: vi.fn(),
  arriveJob: vi.fn(),
  completeJob: vi.fn(),
  incompleteJob: vi.fn(),
}));
vi.mock('../../shared/api/client', () => api);
vi.mock('../../auth/useAuth', () => ({
  useAuth: () => ({ user: { full_name: 'Sam Tech', role: 'technician', organization: { timezone: 'America/Chicago' } } }),
}));

const job = (id: number, status: string, over: Partial<TechnicianJob> = {}): TechnicianJob =>
  ({
    id,
    title: `Job ${id}`,
    customer_name: 'Ada Customer',
    customer_phone: '512-555-0100',
    address: `${id} Main St`,
    postal_code: '78701',
    description: '',
    category: 'hvac',
    is_urgent: false,
    priority: 'normal',
    status,
    scheduled_date: '2026-11-02',
    slot_start: '2026-11-02T15:00:00Z',
    slot_end: '2026-11-02T17:00:00Z',
    slot_is_fixed: true,
    estimated_arrival: '2026-11-02T15:14:00Z',
    estimated_duration_minutes: 60,
    sequence_position: id,
    lat: 30.2,
    lng: -97.7,
    arrived_at: null,
    completed_at: null,
    ...over,
  }) as TechnicianJob;

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  initOrgTimezone('America/Chicago');
  Object.values(api).forEach((fn) => fn.mockReset());
  api.fetchMyJobs.mockResolvedValue([job(1, 'assigned'), job(2, 'assigned')]);
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
    root.render(<TechnicianHome />);
  });
const buttons = () => [...host.querySelectorAll('button')];
const button = (label: string) => {
  const found = buttons().find((b) => b.textContent?.includes(label));
  expect(found, `button "${label}"`).toBeTruthy();
  return found!;
};
const click = (label: string) =>
  act(async () => {
    button(label).click();
  });
const card = (id: number) => host.querySelector(`#job-${id}`)!;
const deferred = <T,>() => {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
};

describe('TechnicianHome', () => {
  it('lists today’s jobs in order, with the three large actions on the current one only', async () => {
    await mount();
    expect([...host.querySelectorAll('article')].map((a) => a.id)).toEqual(['job-1', 'job-2']);
    expect(card(1).getAttribute('aria-current')).toBe('step');
    expect([...card(1).querySelectorAll('[role="group"] button')].map((b) => b.textContent)).toEqual([
      'Arrive',
      'Complete',
      'Couldn’t finish',
    ]);
    expect(card(2).querySelector('[role="group"]')).toBeNull();
  });

  it('only Arrive is available before arriving', async () => {
    await mount();
    expect(button('Arrive').disabled).toBe(false);
    expect(button('Complete').disabled).toBe(true);
    expect(button('Couldn’t finish').disabled).toBe(true);
  });

  it('shows the day’s progress', async () => {
    api.fetchMyJobs.mockResolvedValue([job(1, 'completed'), job(2, 'assigned'), job(3, 'assigned')]);
    await mount();
    expect(host.textContent).toContain('1 of 3 done');
    expect(card(2).getAttribute('aria-current')).toBe('step');
  });

  it('says so when nothing is planned', async () => {
    api.fetchMyJobs.mockResolvedValue([]);
    await mount();
    expect(host.textContent).toContain('No jobs planned for today.');
  });

  it('Arrive sends one request, disables every button while it is sent, then enables Complete', async () => {
    const pending = deferred<TechnicianJob>();
    api.arriveJob.mockReturnValue(pending.promise);
    await mount();
    api.fetchMyJobs.mockResolvedValue([job(1, 'ongoing'), job(2, 'assigned')]); // the server after the tap
    await click('Arrive');
    expect(api.arriveJob).toHaveBeenCalledWith(1);
    expect(buttons().every((b) => b.disabled || b.tagName !== 'BUTTON')).toBe(true);
    await click('Arrive'); // a second tap while sending does nothing
    expect(api.arriveJob).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(job(1, 'ongoing')));
    expect(button('Complete').disabled).toBe(false);
    expect(button('Arrive').disabled).toBe(true);
    expect(card(1).textContent).toContain('Ongoing');
  });

  it('while one job is ongoing the others cannot be started', async () => {
    api.fetchMyJobs.mockResolvedValue([job(1, 'ongoing'), job(2, 'assigned')]);
    await mount();
    expect(button('Arrive here instead').disabled).toBe(true);
    expect(card(2).textContent).toContain('Finish your current job first.');
  });

  it('Complete marks the job done and moves the large buttons to the next one', async () => {
    api.fetchMyJobs.mockResolvedValue([job(1, 'ongoing'), job(2, 'assigned')]);
    const finished = job(1, 'completed', { completed_at: '2026-11-02T16:00:00Z' });
    api.completeJob.mockResolvedValue(finished);
    await mount();
    api.fetchMyJobs.mockResolvedValue([finished, job(2, 'assigned')]); // the server after the tap
    await click('Complete');
    expect(api.completeJob).toHaveBeenCalledWith(1);
    expect(card(1).textContent).toContain('Finished 10:00');
    expect(card(2).getAttribute('aria-current')).toBe('step');
    expect(host.textContent).toContain('1 of 2 done');
  });

  it('Couldn’t finish asks for a reason first and sends nothing until it is given', async () => {
    api.fetchMyJobs.mockResolvedValue([job(1, 'ongoing'), job(2, 'assigned')]);
    await mount();
    await click('Couldn’t finish');
    expect(host.querySelector('[role="dialog"]')).toBeTruthy();
    expect(api.incompleteJob).not.toHaveBeenCalled();
    await click('Send back to the queue');
    expect(api.incompleteJob).not.toHaveBeenCalled();
    expect(host.textContent).toContain('Say what went wrong.');
  });

  it('sends the reason, drops the job from the list and says where it went', async () => {
    api.fetchMyJobs.mockResolvedValue([job(1, 'ongoing'), job(2, 'assigned')]);
    api.incompleteJob.mockResolvedValue(job(1, 'unassigned'));
    await mount();
    api.fetchMyJobs.mockResolvedValue([job(2, 'assigned')]); // the server after the tap
    await click('Couldn’t finish');
    const field = host.querySelector('textarea')!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(field, 'No access to the roof');
      field.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => {
      host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });
    expect(api.incompleteJob).toHaveBeenCalledWith(1, 'No access to the roof');
    expect(host.querySelector('[role="dialog"]')).toBeNull();
    expect(host.querySelector('#job-1')).toBeNull();
    expect(host.textContent).toContain('Sent back to the dispatcher’s queue.');
  });

  it('a refused second arrival shows the message and reloads the truth', async () => {
    api.arriveJob.mockRejectedValue(new ApiError(409, { detail: 'Finish your current job first.' }));
    await mount();
    api.fetchMyJobs.mockResolvedValue([job(1, 'assigned'), job(2, 'ongoing')]);
    await click('Arrive');
    expect(host.querySelector('[role="alert"]')?.textContent).toBe('Finish your current job first.');
    expect(api.fetchMyJobs).toHaveBeenCalledTimes(2);
    expect(card(2).textContent).toContain('Ongoing');
  });

  it('a job the office took away (404) disappears after the reload', async () => {
    api.arriveJob.mockRejectedValue(new ApiError(404, { detail: 'Not found.' }));
    await mount();
    api.fetchMyJobs.mockResolvedValue([job(2, 'assigned')]);
    await click('Arrive');
    expect(host.querySelector('#job-1')).toBeNull();
    expect(card(2).getAttribute('aria-current')).toBe('step');
  });

  it('a dropped connection keeps the job where it was and says to try again', async () => {
    api.arriveJob.mockRejectedValue(new TypeError('network'));
    await mount();
    await click('Arrive');
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('Try again');
    expect(button('Arrive').disabled).toBe(false);
  });

  it('an urgent job with no window says to go as soon as possible', async () => {
    api.fetchMyJobs.mockResolvedValue([job(1, 'assigned', { is_urgent: true, slot_start: null, slot_end: null })]);
    await mount();
    expect(card(1).textContent).toContain('As soon as possible');
    expect(card(1).textContent).not.toContain('No time window');
  });

  it('offers directions and a call link for the customer', async () => {
    await mount();
    const links = [...card(1).querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(links[0]).toContain('https://www.google.com/maps/dir/');
    expect(links[1]).toBe('tel:5125550100');
  });
});
