// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { JobDetail } from '../../shared/api/models';
import JobForm from './JobForm';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({
  createJob: vi.fn(),
  updateJob: vi.fn(),
  pinJob: vi.fn(),
  lookupAddress: vi.fn(),
  fetchSkills: vi.fn(),
  fetchJobCategories: vi.fn(),
  fetchOrganization: vi.fn(),
}));
vi.mock('../../shared/api/client', () => api);
// Leaflet needs a real browser; the map is checked there.
vi.mock('../../shared/map/PinMap', () => ({ default: () => null }));

const org = { work_start: '07:00:00', work_end: '18:00:00', lat: 30.2, lng: -97.7 };
const skills = [
  { id: 1, name: 'HVAC', description: null },
  { id: 2, name: 'Electricians', description: null },
  { id: 3, name: 'Contractors & Handymen', description: null },
];
const categories = [
  { value: 'hvac', label: 'Heating & Air Conditioning', major_skill_ids: [1], minor_skill_ids: [1, 3] },
  { value: 'electrical', label: 'Electricians', major_skill_ids: [2], minor_skill_ids: [2, 3] },
];

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  api.createJob.mockReset().mockResolvedValue({ id: 9, version: 1 });
  api.updateJob.mockReset().mockResolvedValue({ id: 9, version: 2 });
  api.pinJob.mockReset();
  api.lookupAddress.mockReset().mockResolvedValue({ status: 'ok', lat: 30.2, lng: -97.7, label: '1 Main St' });
  api.fetchSkills.mockReset().mockResolvedValue(skills);
  api.fetchJobCategories.mockReset().mockResolvedValue(categories);
  api.fetchOrganization.mockReset().mockResolvedValue(org);
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

const mount = (job?: JobDetail) =>
  act(async () => root.render(<JobForm job={job} onSaved={() => undefined} onCancel={() => undefined} />));
const labelled = (start: string) => {
  const l = [...host.querySelectorAll('label')].find((x) => x.textContent?.trim().startsWith(start));
  expect(l, start).toBeTruthy();
  return l!.querySelector('input,textarea,select') as HTMLInputElement;
};
const type = async (el: HTMLInputElement, value: string) =>
  act(async () => {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
const radio = (group: string, text: string) => {
  const r = [...host.querySelectorAll(`[role=radiogroup][aria-label="${group}"] [role=radio]`)].find(
    (x) => x.textContent === text,
  );
  expect(r, `${group}: ${text}`).toBeTruthy();
  return r as HTMLElement;
};
const press = (el: HTMLElement) => act(async () => el.click());
const submit = () =>
  act(async () => {
    host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });

async function fillNewJob() {
  await mount();
  await type(labelled('Name'), 'Ada Customer');
  await type(host.querySelector('textarea') as unknown as HTMLInputElement, 'AC is blowing warm air');
  await type(labelled('Address'), '1 Main St, Austin, TX 78701');
  await type(labelled('Day'), '2026-11-20');
}

describe('JobForm priority and any-time', () => {
  it('sends a time window and normal priority by default', async () => {
    await fillNewJob();
    await submit();
    expect(api.createJob).toHaveBeenCalledTimes(1);
    const sent = api.createJob.mock.calls[0][0];
    expect(sent.priority).toBe('normal');
    expect(sent.slot_start).toContain('2026-11-20');
    expect(sent).not.toHaveProperty('any_time_on');
  });

  it('sends the day, and no window, for "Any time that day"', async () => {
    await fillNewJob();
    await press(radio('Time on the day', 'Any time that day'));
    expect(host.textContent).toContain('anywhere in your opening hours (07:00–18:00)');
    expect(host.textContent).not.toContain('Available from');
    await submit();
    const sent = api.createJob.mock.calls[0][0];
    expect(sent.any_time_on).toBe('2026-11-20');
    expect(sent).not.toHaveProperty('slot_start');
    expect(sent).not.toHaveProperty('slot_end');
  });

  it('sends the chosen priority', async () => {
    await fillNewJob();
    await press(radio('Priority', 'High'));
    await submit();
    expect(api.createJob.mock.calls[0][0].priority).toBe('high');
  });

  it('shows the server’s message under the any-time note', async () => {
    const { ApiError } = await import('../../shared/api/http');
    api.createJob.mockRejectedValue(new ApiError(400, { any_time_on: ['Set the opening hours in Organization first.'] }));
    await fillNewJob();
    await press(radio('Time on the day', 'Any time that day'));
    await submit();
    expect(host.textContent).toContain('Set the opening hours in Organization first.');
  });

  it('opens an any-time job in any-time mode and saves it back as a day', async () => {
    const job = {
      id: 9, version: 3, status: 'unassigned', title: 'T', description: 'd', customer_name: 'A',
      customer_phone: null, category: 'hvac', is_urgent: false, priority: 'high', address: '1 Main St',
      postal_code: '78701', slot_is_fixed: false, estimated_duration_minutes: 60,
      slot_start: '2026-11-20T13:00:00Z', slot_end: '2026-11-20T24:00:00Z',
      acceptable_skills: [{ id: 1, name: 'HVAC' }], technician: null, history: [],
    } as unknown as JobDetail;
    await mount(job);
    expect(radio('Time on the day', 'Any time that day').getAttribute('aria-checked')).toBe('true');
    expect(radio('Priority', 'High').getAttribute('aria-checked')).toBe('true');
    await submit();
    const sent = api.updateJob.mock.calls[0][1];
    expect(sent.any_time_on).toMatch(/^2026-11-20$/);
    expect(sent).not.toHaveProperty('slot_start');
    expect(sent.priority).toBe('high');
  });

  it('lets priority change on a planned job while the window stays locked', async () => {
    const job = {
      id: 9, version: 3, status: 'assigned', title: 'T', description: 'd', customer_name: 'A',
      customer_phone: null, category: 'hvac', is_urgent: false, priority: 'normal', address: '1 Main St',
      postal_code: '78701', slot_is_fixed: true, estimated_duration_minutes: 60,
      slot_start: '2026-11-20T15:00:00Z', slot_end: '2026-11-20T17:00:00Z',
      acceptable_skills: [{ id: 1, name: 'HVAC' }], technician: null, history: [],
    } as unknown as JobDetail;
    await mount(job);
    expect((radio('Time on the day', 'Any time that day') as HTMLButtonElement).disabled).toBe(true);
    expect((radio('Priority', 'High') as HTMLButtonElement).disabled).toBe(false);
    await press(radio('Priority', 'High'));
    await submit();
    const sent = api.updateJob.mock.calls[0][1];
    expect(sent.priority).toBe('high');
    expect(sent).not.toHaveProperty('slot_start');
    expect(sent).not.toHaveProperty('any_time_on');
  });
});

const skillBox = (name: string) => {
  const l = [...host.querySelectorAll('fieldset label')].find((x) => x.textContent?.trim() === name);
  expect(l, name).toBeTruthy();
  return l!.querySelector('input') as HTMLInputElement;
};

describe('JobForm minor and major jobs', () => {
  it('is a major job by default and sends that', async () => {
    await fillNewJob();
    await submit();
    expect(api.createJob.mock.calls[0][0].complexity).toBe('major');
  });

  it('sends minor when the dispatcher says so', async () => {
    await fillNewJob();
    await press(radio('How big is the job', 'Minor'));
    await submit();
    expect(api.createJob.mock.calls[0][0].complexity).toBe('minor');
  });

  it('pre-selects the specialist for a major job and adds the helpers for a minor one', async () => {
    await mount();
    await press(radio('Type of work', 'Electricians'));
    expect(skillBox('Electricians').checked).toBe(true);
    expect(skillBox('Contractors & Handymen').checked).toBe(false);
    await press(radio('How big is the job', 'Minor'));
    expect(skillBox('Electricians').checked).toBe(true);
    expect(skillBox('Contractors & Handymen').checked).toBe(true);
    await press(radio('How big is the job', 'Major'));
    expect(skillBox('Contractors & Handymen').checked).toBe(false);
  });

  it('leaves skills to the server until the chips are touched, so the server applies the same rule', async () => {
    await fillNewJob();
    await press(radio('How big is the job', 'Minor'));
    await submit();
    expect(api.createJob.mock.calls[0][0]).not.toHaveProperty('skill_ids');
  });

  it('keeps the dispatcher’s own skill choice when the job size changes', async () => {
    await mount();
    await press(radio('Type of work', 'Electricians'));
    await press(skillBox('Contractors & Handymen'));
    await press(radio('How big is the job', 'Minor'));
    expect(skillBox('Contractors & Handymen').checked).toBe(true);
    await press(radio('How big is the job', 'Major'));
    expect(skillBox('Contractors & Handymen').checked).toBe(true); // touched: it stays
  });
});
