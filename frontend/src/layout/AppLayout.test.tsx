// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AppLayout from './AppLayout';
import { navItems } from './navItems';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const auth = vi.hoisted(() => ({ role: 'dispatcher', signOut: vi.fn() }));
vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    user: {
      full_name: 'Alex Morgan',
      role: auth.role,
      organization: { name: 'Brightline', timezone: 'America/Chicago' },
    },
    signOut: auth.signOut,
  }),
}));

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  auth.role = 'dispatcher';
  auth.signOut.mockReset().mockResolvedValue(undefined);
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
  document.body.style.overflow = '';
});

const mount = (path = '/jobs') =>
  act(async () => {
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppLayout />}>
            {['/jobs', '/map', '/plan', '/tech', '/users'].map((p) => (
              <Route key={p} path={p} element={<h1>Page {p}</h1>} />
            ))}
          </Route>
        </Routes>
      </MemoryRouter>,
    );
  });
const menuButton = () => host.querySelector<HTMLButtonElement>('button[aria-label="Open menu"]');
const drawer = () => document.querySelector<HTMLElement>('[role="dialog"]');
const open = async () => {
  menuButton()!.focus();
  await act(async () => menuButton()!.click());
};
const press = (key: string, shiftKey = false) =>
  act(async () => {
    (document.activeElement ?? document.body).dispatchEvent(
      new KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true }),
    );
  });

describe('navItems', () => {
  it('gives each role only its own pages', () => {
    expect(navItems('technician').map((i) => i.label)).toEqual(['My jobs']);
    expect(navItems('dispatcher').map((i) => i.label)).not.toContain('Team');
    expect(navItems('head_dispatcher').map((i) => i.label)).toContain('Team');
  });
});

describe('AppLayout drawer', () => {
  it('is closed until the menu button is pressed', async () => {
    await mount();
    expect(drawer()).toBeNull();
    expect(menuButton()!.getAttribute('aria-expanded')).toBe('false');
    await open();
    expect(drawer()).toBeTruthy();
    expect(menuButton()!.getAttribute('aria-expanded')).toBe('true');
    expect(drawer()!.getAttribute('aria-modal')).toBe('true');
  });

  it('lists the dispatcher’s pages and marks the current one', async () => {
    await mount('/map');
    await open();
    const links = [...drawer()!.querySelectorAll('a')];
    expect(links.map((a) => a.textContent)).toEqual([
      'Dashboard', 'Jobs', 'Plan', 'Map', 'Technicians', 'Organization',
    ]);
    expect(links.find((a) => a.textContent === 'Map')!.getAttribute('aria-current')).toBe('page');
  });

  it('moves focus into the drawer, and the page behind does not scroll', async () => {
    await mount();
    await open();
    expect(drawer()!.contains(document.activeElement)).toBe(true);
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('Escape closes it and focus goes back to the menu button', async () => {
    await mount();
    await open();
    await press('Escape');
    expect(drawer()).toBeNull();
    expect(document.activeElement).toBe(menuButton());
    expect(document.body.style.overflow).toBe('');
  });

  it('the Close button and a tap on the dim area close it', async () => {
    await mount();
    await open();
    await act(async () => {
      [...drawer()!.querySelectorAll('button')].find((b) => b.textContent === 'Close')!.click();
    });
    expect(drawer()).toBeNull();
    await open();
    await act(async () => {
      (drawer()!.previousElementSibling as HTMLElement).click(); // the dim area
    });
    expect(drawer()).toBeNull();
  });

  it('choosing a page opens it and closes the drawer', async () => {
    await mount('/jobs');
    await open();
    await act(async () => {
      [...drawer()!.querySelectorAll('a')].find((a) => a.textContent === 'Plan')!.click();
    });
    expect(drawer()).toBeNull();
    expect(host.textContent).toContain('Page /plan');
  });

  it('keeps Tab inside: from the last control it wraps to the first, and back', async () => {
    await mount();
    await open();
    const items = [...drawer()!.querySelectorAll<HTMLElement>('a[href], button')];
    items[items.length - 1].focus();
    await press('Tab');
    expect(document.activeElement).toBe(items[0]);
    await press('Tab', true);
    expect(document.activeElement).toBe(items[items.length - 1]);
  });

  it('signs out from the drawer', async () => {
    await mount();
    await open();
    await act(async () => {
      [...drawer()!.querySelectorAll('button')].find((b) => b.textContent === 'Sign out')!.click();
    });
    expect(auth.signOut).toHaveBeenCalledTimes(1);
  });

  it('shows Team to a head dispatcher', async () => {
    auth.role = 'head_dispatcher';
    await mount();
    await open();
    expect([...drawer()!.querySelectorAll('a')].map((a) => a.textContent)).toContain('Team');
  });
});

describe('AppLayout for a technician', () => {
  it('has no menu to open, just the brand, the theme switch and Sign out', async () => {
    auth.role = 'technician';
    await mount('/tech');
    expect(menuButton()).toBeNull();
    expect(host.querySelector('aside')).toBeNull();
    expect(host.querySelector('header')!.textContent).toContain('Brightline');
    expect([...host.querySelectorAll('button')].map((b) => b.textContent)).toEqual([
      'Dark mode: off',
      'Sign out',
    ]);
  });
});
