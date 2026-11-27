// Light or dark. The person's choice is kept on this device; without one, the system's
// preference applies (index.css). The page applies a saved choice before first paint
// (the small script in index.html), so there is no flash of the wrong theme.
export type Theme = 'light' | 'dark';

const KEY = 'fd-theme';

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null; // storage blocked: fall back to the system setting
  }
}

/** The theme on screen now: the person's choice, else what the system prefers. */
export function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === 'light' || set === 'dark') return set;
  const saved = stored();
  if (saved) return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/** Show this theme and remember it on this device (remembering is best effort). */
export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* the choice still holds for this visit */
  }
}
