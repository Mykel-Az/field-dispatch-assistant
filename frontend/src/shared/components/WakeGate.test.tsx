// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SHOW_HINT_AFTER_SECONDS, SHOW_SPLASH_AFTER_MS, WakeGate } from './WakeGate';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root;
let host: HTMLElement;

beforeEach(() => {
  vi.useFakeTimers();
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.useRealTimers();
});

const mount = (probe: (s: AbortSignal) => Promise<boolean>, extra = {}) =>
  act(() =>
    root.render(
      <WakeGate probe={probe} {...extra}>
        <p>the app</p>
      </WakeGate>,
    ),
  );

const advance = async (ms: number) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

describe('WakeGate', () => {
  it('shows the app straight away, with no splash, when the backend is already awake', async () => {
    mount(() => Promise.resolve(true));
    await advance(0);
    expect(host.textContent).toContain('the app');
    expect(host.textContent).not.toContain('Waking up');
  });

  it('shows the pulsing logo when slow, adds the explanation only after a few seconds, then the app', async () => {
    let awake = false;
    mount(() => Promise.resolve(awake));
    const hint = () => host.querySelector('p')!;

    await advance(SHOW_SPLASH_AFTER_MS + 100);
    expect(host.querySelector('[role="status"]')).not.toBeNull();
    expect(host.querySelector('svg')!.getAttribute('class')).toContain('animate-logo-pulse');
    expect(hint().className).toContain('opacity-0'); // text is there but invisible

    await advance((SHOW_HINT_AFTER_SECONDS + 0.5) * 1000);
    expect(hint().className).toContain('opacity-75');
    expect(host.textContent).toContain('Waking up the server');

    awake = true;
    await advance(2_500); // next retry
    expect(host.textContent).toContain('the app');
    expect(host.textContent).not.toContain('Waking up');
  });

  it('abandons a hung attempt and tries again', async () => {
    let calls = 0;
    const probe = (signal: AbortSignal) =>
      new Promise<boolean>((resolve) => {
        calls += 1;
        if (calls === 1) signal.addEventListener('abort', () => resolve(false)); // hangs
        else resolve(true);
      });
    mount(probe, { attemptTimeoutMs: 3_000, retryDelayMs: 500 });
    await advance(3_000); // attempt 1 aborted
    await advance(500); // attempt 2
    expect(calls).toBe(2);
    expect(host.textContent).toContain('the app');
  });

  it('treats a rejected probe like "not yet", not a crash', async () => {
    let calls = 0;
    mount(() => (++calls < 3 ? Promise.reject(new Error('502')) : Promise.resolve(true)), {
      retryDelayMs: 500,
    });
    await advance(1_100);
    expect(host.textContent).toContain('the app');
  });

  it('gives up after the limit, then Try again starts over', async () => {
    let awake = false;
    mount(() => Promise.resolve(awake), { giveUpMs: 10_000, retryDelayMs: 1_000 });
    await advance(10_100);
    expect(host.textContent).toContain("couldn't reach the server");
    expect(host.querySelector('[role="alert"]')).not.toBeNull();

    awake = true;
    const button = host.querySelector('button')!;
    act(() => button.click());
    await advance(0);
    expect(host.textContent).toContain('the app');
  });
});
