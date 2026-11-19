// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { notifyJobsChanged, POLL_INTERVAL_MS, usePolling } from './usePolling';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root;
let host: HTMLElement;
let visibility: DocumentVisibilityState;
const refresh = vi.fn();

function Probe() {
  usePolling(refresh);
  return null;
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-11-19T12:00:00Z'));
  visibility = 'visible';
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
  refresh.mockReset();
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  act(() => root.render(<Probe />));
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.useRealTimers();
});

const tick = (ms: number) => act(async () => void vi.advanceTimersByTime(ms));

describe('usePolling', () => {
  it('refreshes every interval while the tab is visible', async () => {
    await tick(POLL_INTERVAL_MS - 1);
    expect(refresh).not.toHaveBeenCalled();
    await tick(1);
    expect(refresh).toHaveBeenCalledTimes(1);
    await tick(POLL_INTERVAL_MS);
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it('makes no request while the tab is hidden', async () => {
    visibility = 'hidden';
    await tick(POLL_INTERVAL_MS * 4);
    expect(refresh).not.toHaveBeenCalled();
  });

  it('refreshes once when the tab comes back, even though focus fires too', async () => {
    visibility = 'hidden';
    await tick(POLL_INTERVAL_MS * 2);
    visibility = 'visible';
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
      window.dispatchEvent(new Event('focus'));
    });
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('does not refresh on visibilitychange to hidden', () => {
    visibility = 'hidden';
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    expect(refresh).not.toHaveBeenCalled();
  });

  it('refreshes at once after the user changes a job, never debounced', () => {
    act(() => notifyJobsChanged());
    act(() => notifyJobsChanged());
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it('stops everything on unmount', async () => {
    act(() => root.unmount());
    await tick(POLL_INTERVAL_MS * 2);
    act(() => window.dispatchEvent(new Event('focus')));
    expect(refresh).not.toHaveBeenCalled();
    root = createRoot(host); // so afterEach can unmount
  });
});
