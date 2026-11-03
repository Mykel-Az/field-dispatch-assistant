import { useCallback, useEffect, useRef, useState } from 'react';

// Free-tier hosting puts the backend to sleep when idle, and the first request
// after that takes up to about a minute (ADR-018). This hook asks "is it awake
// yet?" until it is, so the app can show a friendly screen instead of a blank
// page or a raw error.

export type WakeState = 'checking' | 'ready' | 'failed';

export interface WakeOptions {
  /** Resolves true when the backend answers. Should honour the abort signal. */
  probe: (signal: AbortSignal) => Promise<boolean>;
  /** One attempt is abandoned after this long (a sleeping host can hang). */
  attemptTimeoutMs?: number;
  /** Pause between attempts. */
  retryDelayMs?: number;
  /** Stop trying after this long and offer a retry button. */
  giveUpMs?: number;
}

export const ATTEMPT_TIMEOUT_MS = 10_000;
export const RETRY_DELAY_MS = 2_000;
export const GIVE_UP_MS = 90_000;

export function useWakeUp({
  probe,
  attemptTimeoutMs = ATTEMPT_TIMEOUT_MS,
  retryDelayMs = RETRY_DELAY_MS,
  giveUpMs = GIVE_UP_MS,
}: WakeOptions) {
  const [state, setState] = useState<WakeState>('checking');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [run, setRun] = useState(0);

  const latestProbe = useRef(probe);
  useEffect(() => {
    latestProbe.current = probe;
  });

  useEffect(() => {
    let stopped = false;
    const started = Date.now();
    let controller: AbortController | null = null;
    let attemptTimer: number | undefined;
    let retryTimer: number | undefined;

    const stop = (next: WakeState) => {
      if (stopped) return;
      stopped = true;
      cleanup();
      setState(next);
    };
    const cleanup = () => {
      window.clearInterval(clock);
      window.clearTimeout(giveUp);
      window.clearTimeout(attemptTimer);
      window.clearTimeout(retryTimer);
      controller?.abort();
    };

    const clock = window.setInterval(
      () => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    const giveUp = window.setTimeout(() => stop('failed'), giveUpMs);

    const attempt = async () => {
      if (stopped) return;
      const own = new AbortController();
      controller = own;
      attemptTimer = window.setTimeout(() => own.abort(), attemptTimeoutMs);
      const ok = await latestProbe.current(own.signal).catch(() => false);
      window.clearTimeout(attemptTimer);
      if (stopped) return;
      if (ok) stop('ready');
      else retryTimer = window.setTimeout(attempt, retryDelayMs);
    };
    void attempt();

    return () => {
      stopped = true;
      cleanup();
    };
  }, [run, attemptTimeoutMs, retryDelayMs, giveUpMs]);

  const retry = useCallback(() => {
    setState('checking');
    setElapsedSeconds(0);
    setRun((n) => n + 1);
  }, []);

  return { state, elapsedSeconds, retry };
}
