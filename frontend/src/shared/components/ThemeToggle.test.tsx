// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ThemeToggle from './ThemeToggle';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  delete document.documentElement.dataset.theme;
  localStorage.clear();
  vi.stubGlobal('matchMedia', () => ({ matches: false }));
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

describe('ThemeToggle', () => {
  it('switches the page to dark and back, and says which it is', async () => {
    await act(async () => root.render(<ThemeToggle />));
    const button = host.querySelector('button')!;
    expect(button.getAttribute('aria-pressed')).toBe('false');
    expect(button.textContent).toBe('Dark mode: off');

    await act(async () => button.click());
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(button.getAttribute('aria-pressed')).toBe('true');
    expect(button.textContent).toBe('Dark mode: on');

    await act(async () => button.click());
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('starts on when the system prefers dark', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    await act(async () => root.render(<ThemeToggle />));
    expect(host.querySelector('button')!.getAttribute('aria-pressed')).toBe('true');
  });
});
