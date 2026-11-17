// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../shared/api/http';
import type { JobDetail } from '../../shared/api/models';
import LocationDialog from './LocationDialog';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ pinJob: vi.fn() }));
vi.mock('../../shared/api/client', () => api);
// Leaflet needs a real browser; the map is checked there. Here it is a button that "picks" a spot.
vi.mock('../../shared/map/PinMap', () => ({
  default: ({ onPick, office }: { onPick: (p: { lat: number; lng: number }) => void; office: unknown }) => (
    <button type="button" data-office={office ? 'yes' : 'no'} onClick={() => onPick({ lat: 30.5, lng: -97.5 })}>
      pick
    </button>
  ),
}));

const job = { id: 5, version: 3, address: '12 Oak St', lat: 30.1, lng: -97.1 } as unknown as JobDetail;

let root: Root;
let host: HTMLElement;
const onChanged = vi.fn();
const onClose = vi.fn();
beforeEach(() => {
  api.pinJob.mockReset().mockResolvedValue({ ...job, version: 4 });
  onChanged.mockReset();
  onClose.mockReset();
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

const mount = () =>
  act(async () =>
    root.render(<LocationDialog job={job} office={{ lat: 30, lng: -97 }} onChanged={onChanged} onClose={onClose} />),
  );
const button = (text: string) => {
  const b = [...host.querySelectorAll('button')].find((x) => x.textContent?.trim() === text);
  expect(b, text).toBeTruthy();
  return b as HTMLButtonElement;
};
const press = (text: string) => act(async () => button(text).click());

describe('LocationDialog', () => {
  it('is a modal dialog showing the customer’s address and the office on the map', async () => {
    await mount();
    expect(host.querySelector('[role=dialog][aria-modal=true]')).toBeTruthy();
    expect(host.textContent).toContain('12 Oak St');
    expect(button('pick').dataset.office).toBe('yes');
  });

  it('cannot save before the pin is moved', async () => {
    await mount();
    expect(button('Save location').disabled).toBe(true);
  });

  it('saves the moved pin with the job version, then reports and closes', async () => {
    await mount();
    await press('pick');
    expect(host.textContent).toContain('approximate');
    await press('Save location');
    expect(api.pinJob).toHaveBeenCalledWith(5, 30.5, -97.5, 3);
    expect(onChanged).toHaveBeenCalledWith(expect.objectContaining({ version: 4 }));
    expect(onClose).toHaveBeenCalled();
  });

  it('Cancel and Escape close without saving', async () => {
    await mount();
    await press('pick');
    await press('Cancel');
    expect(onClose).toHaveBeenCalledTimes(1);
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(api.pinJob).not.toHaveBeenCalled();
  });

  it('undo move puts the dialog back to unchanged', async () => {
    await mount();
    await press('pick');
    await press('Undo move');
    expect(button('Save location').disabled).toBe(true);
  });

  it('stays open with the reason, and asks for a reload, when someone else changed the job', async () => {
    api.pinJob.mockRejectedValue(new ApiError(409, { detail: 'This job was changed by someone else.' }));
    await mount();
    await press('pick');
    await press('Save location');
    expect(host.querySelector('[role=alert]')?.textContent).toContain('changed by someone else');
    expect(onChanged).toHaveBeenCalledWith(null);
    expect(onClose).not.toHaveBeenCalled();
  });
});
