// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ReasonDialog from './ReasonDialog';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

const show = (props: Partial<React.ComponentProps<typeof ReasonDialog>> = {}) => {
  const onSend = vi.fn();
  const onClose = vi.fn();
  act(() => {
    root.render(<ReasonDialog jobTitle="Fix AC" busy={false} error="" onSend={onSend} onClose={onClose} {...props} />);
  });
  return { onSend, onClose };
};
const type = (el: HTMLTextAreaElement, value: string) =>
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
const submit = () =>
  act(() => {
    host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });

describe('ReasonDialog', () => {
  it('names the job and says it goes back to the queue', () => {
    show();
    expect(host.querySelector('[role="dialog"]')?.textContent).toContain('“Fix AC” goes back to the dispatcher’s queue');
  });

  it('will not send an empty or blank reason', () => {
    const { onSend } = show();
    submit();
    expect(host.textContent).toContain('Say what went wrong.');
    type(host.querySelector('textarea')!, '   ');
    submit();
    expect(onSend).not.toHaveBeenCalled();
  });

  it('sends the trimmed reason', () => {
    const { onSend } = show();
    type(host.querySelector('textarea')!, '  Part not on the truck ');
    submit();
    expect(onSend).toHaveBeenCalledWith('Part not on the truck');
  });

  it('disables both buttons and the field while sending, and does not send twice', () => {
    const { onSend } = show({ busy: true });
    const buttons = [...host.querySelectorAll('button')];
    expect(buttons.map((b) => b.disabled)).toEqual([true, true]);
    expect(host.querySelector('textarea')!.disabled).toBe(true);
    expect(buttons[0].textContent).toBe('Sending…');
    submit();
    expect(onSend).not.toHaveBeenCalled();
  });

  it('closes on Escape, but not while sending', () => {
    const first = show();
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(first.onClose).toHaveBeenCalledTimes(1);
    const second = show({ busy: true });
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(second.onClose).not.toHaveBeenCalled();
  });

  it('shows the server’s error', () => {
    show({ error: 'Something went wrong' });
    expect(host.querySelector('[role="alert"]')?.textContent).toBe('Something went wrong');
  });
});
