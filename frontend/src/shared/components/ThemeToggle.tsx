import { useState } from 'react';
import { currentTheme, setTheme, type Theme } from '../theme';
import { ui } from '../ui';

/** A switch between the light and dark theme. */
export default function ThemeToggle() {
  const [theme, setCurrent] = useState<Theme>(currentTheme);
  const dark = theme === 'dark';
  return (
    <button
      type="button"
      className={ui.btnSmall}
      aria-pressed={dark}
      onClick={() => {
        const next: Theme = dark ? 'light' : 'dark';
        setTheme(next);
        setCurrent(next);
      }}
    >
      Dark mode: {dark ? 'on' : 'off'}
    </button>
  );
}
