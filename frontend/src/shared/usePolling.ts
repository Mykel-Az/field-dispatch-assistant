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

/**
 * Keeps a view fresh: calls `refresh` every `ms` while the tab is visible, as
 * soon as the tab becomes visible or the window regains focus, and whenever
 * notifyJobsChanged() is called. The first load is the caller's job (it also
 * depends on the filters). `refresh` may change identity freely.
 */
export function usePolling(refresh: () => void, ms = 30_000) {
  const latest = useRef(refresh);
  useEffect(() => {
    latest.current = refresh;
  });

  useEffect(() => {
    const now = () => latest.current();
    const whenVisible = () => document.visibilityState === 'visible' && now();
    const timer = window.setInterval(whenVisible, ms);
    const listener = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel(CHANNEL);
    listener?.addEventListener('message', now);
    document.addEventListener('visibilitychange', whenVisible);
    window.addEventListener('focus', whenVisible);
    window.addEventListener('jobs:changed', now);
    return () => {
      window.clearInterval(timer);
      listener?.close();
      document.removeEventListener('visibilitychange', whenVisible);
      window.removeEventListener('focus', whenVisible);
      window.removeEventListener('jobs:changed', now);
    };
  }, [ms]);
}
