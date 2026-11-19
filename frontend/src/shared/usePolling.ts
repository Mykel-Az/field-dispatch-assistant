import { useEffect, useRef } from 'react';

// "Own actions" (assign, pin, edit, cancel) tell every open map and list to
// refresh now, including ones open in another tab of the same browser.
const CHANNEL = 'field-dispatch-jobs';
const sender = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel(CHANNEL);

/** Call after any change a dispatcher makes to a job. */
export function notifyJobsChanged() {
  sender?.postMessage('changed');
  window.dispatchEvent(new Event('jobs:changed')); // this tab too
}

/** Why 30 s: ADR-009. Own actions refresh at once, so this only bounds how late other people's changes show. */
export const POLL_INTERVAL_MS = 30_000;
// Returning to a tab fires both `visibilitychange` and `focus`; one refresh is enough.
const RETURN_DEBOUNCE_MS = 1_000;

/**
 * Keeps a view fresh: calls `refresh` every `ms` while the tab is visible (a
 * hidden tab makes no requests), as soon as the tab becomes visible or the
 * window regains focus, and whenever notifyJobsChanged() is called. The first
 * load is the caller's job (it also depends on the filters). `refresh` may
 * change identity freely.
 */
export function usePolling(refresh: () => void, ms = POLL_INTERVAL_MS) {
  const latest = useRef(refresh);
  useEffect(() => {
    latest.current = refresh;
  });

  useEffect(() => {
    const now = () => latest.current();
    const whenVisible = () => document.visibilityState === 'visible' && now();
    let lastReturn = -Infinity;
    const onReturn = () => {
      const t = Date.now();
      if (t - lastReturn < RETURN_DEBOUNCE_MS) return;
      lastReturn = t;
      whenVisible();
    };
    const timer = window.setInterval(whenVisible, ms);
    const listener = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel(CHANNEL);
    listener?.addEventListener('message', now);
    document.addEventListener('visibilitychange', onReturn);
    window.addEventListener('focus', onReturn);
    window.addEventListener('jobs:changed', now);
    return () => {
      window.clearInterval(timer);
      listener?.close();
      document.removeEventListener('visibilitychange', onReturn);
      window.removeEventListener('focus', onReturn);
      window.removeEventListener('jobs:changed', now);
    };
  }, [ms]);
}
