import { useEffect, useState, type ReactNode } from 'react';
import { probeHealth } from '../api/http';
import { ui } from '../ui';
import { useWakeUp, type WakeOptions } from '../wakeUp';
import { BrandMark } from './BrandMark';

// A warm backend answers in well under a second; showing the logo for that
// long would only flash. The pulsing logo appears if the wait is noticeable.
export const SHOW_SPLASH_AFTER_MS = 800;
// The explanation only appears when the wait is clearly not a blip.
export const SHOW_HINT_AFTER_SECONDS = 6;

// Soft teal wash with a lighter glow behind the logo. Tokens only (index.css).
const backdrop =
  'min-h-screen grid place-items-center px-6 bg-brand-soft text-brand-ink bg-[radial-gradient(circle_at_50%_45%,var(--surface)_0%,transparent_60%)]';

/** Holds the app back until the backend is awake (ADR-018). */
export function WakeGate({
  children,
  probe = probeHealth,
  ...timing
}: { children: ReactNode } & Partial<WakeOptions>) {
  const { state, elapsedSeconds, retry } = useWakeUp({ probe, ...timing });
  const [noticeable, setNoticeable] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setNoticeable(true), SHOW_SPLASH_AFTER_MS);
    return () => window.clearTimeout(timer);
  }, []);

  if (state === 'ready') return <>{children}</>;

  if (state === 'failed') {
    return (
      <main className={backdrop}>
        <div className="max-w-sm text-center" role="alert">
          <BrandMark className="mx-auto mb-6 size-20 sm:size-24" />
          <h1 className="mb-2 text-2xl font-bold tracking-tight">We couldn't reach the server</h1>
          <p className="mb-5 text-sm opacity-80">
            It didn't wake up in time. This is usually temporary; check your connection and try
            again.
          </p>
          <button type="button" className={ui.btn} onClick={retry}>
            Try again
          </button>
        </div>
      </main>
    );
  }

  if (!noticeable) return <div className={backdrop} />;

  return (
    <main className={backdrop}>
      <div className="flex flex-col items-center text-center" role="status" aria-live="polite">
        <BrandMark className="size-24 animate-logo-pulse sm:size-32 lg:size-40 motion-reduce:animate-none" />
        <span className="sr-only">Loading</span>
        <p
          className={`mt-8 max-w-xs text-xs transition-opacity duration-1000 sm:text-sm ${
            elapsedSeconds >= SHOW_HINT_AFTER_SECONDS ? 'opacity-75' : 'opacity-0'
          }`}
        >
          Waking up the server. This demo runs on free hosting that sleeps when idle, so the first
          load can take a minute.
        </p>
      </div>
    </main>
  );
}
