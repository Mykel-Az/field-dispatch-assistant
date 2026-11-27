// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { currentTheme, setTheme } from './theme';

const prefers = (dark: boolean) =>
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: dark && q.includes('dark') }));

beforeEach(() => {
  delete document.documentElement.dataset.theme;
  localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe('theme', () => {
  it('follows the system when nothing was chosen', () => {
    prefers(true);
    expect(currentTheme()).toBe('dark');
    prefers(false);
    expect(currentTheme()).toBe('light');
  });

  it('shows and remembers the choice, which beats the system', () => {
    prefers(true);
    setTheme('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem('fd-theme')).toBe('light');
    expect(currentTheme()).toBe('light');
  });

  it('uses a saved choice that the page has not applied yet', () => {
    prefers(false);
    localStorage.setItem('fd-theme', 'dark');
    expect(currentTheme()).toBe('dark');
  });

  it('ignores a saved value it does not know', () => {
    prefers(false);
    localStorage.setItem('fd-theme', 'purple');
    expect(currentTheme()).toBe('light');
  });

  it('still switches when storage is blocked', () => {
    prefers(false);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(() => setTheme('dark')).not.toThrow();
    expect(currentTheme()).toBe('dark');
    vi.restoreAllMocks();
  });
});
