// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../shared/api/http';
import type { Organization } from '../../shared/api/models';
import OrganizationPage from './OrganizationPage';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ fetchOrganization: vi.fn(), updateOrganization: vi.fn() }));
vi.mock('../../shared/api/client', () => api);
const auth = vi.hoisted(() => ({ role: 'head_dispatcher' }));
vi.mock('../../auth/useAuth', () => ({
  useAuth: () => ({ user: { role: auth.role }, refreshUser: vi.fn().mockResolvedValue(undefined) }),
}));

const org: Organization = {
  id: 1, name: 'Acme', email: 'a@b.co', phone: '', address: '1 Main St', lat: 30.2, lng: -97.7,
  geocode_status: 'ok', timezone: 'America/Chicago', work_start: '08:00:00', work_end: '17:00:00',
  scoring_strategy: 'balanced', max_jobs_per_tech_per_day: 3, is_configured: true, version: 4,
};

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  auth.role = 'head_dispatcher';
  api.fetchOrganization.mockReset().mockResolvedValue(org);
  api.updateOrganization.mockReset().mockResolvedValue({ ...org, version: 5 });
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

const mount = () => act(async () => root.render(<OrganizationPage />));
const field = (label: string) => {
  const el = [...host.querySelectorAll('label')].find((l) => l.textContent?.startsWith(label));
  expect(el, `field "${label}"`).toBeTruthy();
  return el!.querySelector('input,select') as HTMLInputElement | HTMLSelectElement;
};
const type = async (el: HTMLInputElement | HTMLSelectElement, value: string) => {
  const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, value);
    el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }));
  });
};
const save = () =>
  act(async () => {
    host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });

describe('OrganizationPage planning settings', () => {
  it('shows the saved daily limit and strategy', async () => {
    await mount();
    expect(field('Most jobs per technician per day').value).toBe('3');
    expect(field('How the planner chooses a technician').value).toBe('balanced');
  });

  it('saves a new limit as a number, with the strategy', async () => {
    await mount();
    await type(field('Most jobs per technician per day'), '5');
    await type(field('How the planner chooses a technician'), 'nearest');
    await save();
    expect(api.updateOrganization).toHaveBeenCalledWith(
      expect.objectContaining({ version: 4, max_jobs_per_tech_per_day: 5, scoring_strategy: 'nearest' }),
    );
    expect(host.textContent).toContain('Saved.');
  });

  it('shows the server message next to the field when the limit is rejected', async () => {
    api.updateOrganization.mockRejectedValue(
      new ApiError(400, { max_jobs_per_tech_per_day: ['Ensure this value is less than or equal to 10.'] }),
    );
    await mount();
    await type(field('Most jobs per technician per day'), '50');
    await save();
    expect(host.textContent).toContain('less than or equal to 10');
  });

  it('is read-only for a dispatcher', async () => {
    auth.role = 'dispatcher';
    await mount();
    expect(field('Most jobs per technician per day').disabled).toBe(true);
    expect(field('How the planner chooses a technician').disabled).toBe(true);
  });
});

describe('OrganizationPage time zone rule', () => {
  const locked = () =>
    new ApiError(409, {
      detail: 'The time zone cannot change while 2 jobs are assigned or in progress. Finish or unassign them first.',
      code: 'timezone_locked',
    });

  it('shows the server message at the time zone field and keeps the choice on screen', async () => {
    api.updateOrganization.mockRejectedValue(locked());
    await mount();
    await type(field('Time zone'), 'America/Los_Angeles');
    await save();
    const alert = [...host.querySelectorAll('[role="alert"]')].map((e) => e.textContent).join(' ');
    expect(alert).toContain('2 jobs are assigned or in progress');
    expect(alert).not.toContain('Someone else');
    expect(field('Time zone').value).toBe('America/Los_Angeles');
    expect(api.fetchOrganization).toHaveBeenCalledTimes(1); // no reload: nothing was stale
    expect(host.textContent).not.toContain('Saved.');
  });

  it('still treats a stale-version 409 as "someone else saved first" and reloads', async () => {
    api.updateOrganization.mockRejectedValue(
      new ApiError(409, { detail: 'This record was changed by someone else. Reload it.' }),
    );
    await mount();
    await save();
    expect(host.textContent).toContain('Someone else changed these settings');
    expect(api.fetchOrganization).toHaveBeenCalledTimes(2);
  });

  it('explains the rule before anyone tries', async () => {
    await mount();
    expect(host.textContent).toContain('cannot be changed while a job is assigned or in progress');
  });
});
