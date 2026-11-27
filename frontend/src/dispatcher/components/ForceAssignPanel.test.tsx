// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { JobDetail } from '../../shared/api/models';
import ForceAssignPanel from './ForceAssignPanel';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ forceAssignJob: vi.fn(), fetchJob: vi.fn() }));
vi.mock('../../shared/api/client', () => api);

const job = { id: 9, version: 3, title: 'No heat' } as unknown as JobDetail;
const result = (over = {}) => ({
  job,
  bumped_job_ids: [],
  estimated_arrival: '2026-11-17T15:40:00Z',
  sla_label: 'ok',
  slack_minutes: 25,
  dry_run: true,
  ...over,
});

let root: Root;
let host: HTMLElement;
const onChanged = vi.fn();
beforeEach(() => {
  api.forceAssignJob.mockReset();
  api.fetchJob.mockReset();
  onChanged.mockReset();
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
    root.render(<ForceAssignPanel job={job} technicianId={4} technicianName="Dana" onChanged={onChanged} />),
  );
const button = () => host.querySelector('button') as HTMLButtonElement;

describe('ForceAssignPanel', () => {
  it('asks the server for a dry run first and says nothing is affected when nobody is bumped', async () => {
    api.forceAssignJob.mockResolvedValue(result());
    await mount();
    expect(api.forceAssignJob).toHaveBeenCalledWith(9, 4, 3, true);
    expect(host.textContent).toContain('No other job is affected');
    expect(host.textContent).toContain('25 min to spare');
    expect(button().textContent).toBe('Force assign');
  });

  it('names the jobs that go back to the queue, by title', async () => {
    api.forceAssignJob.mockResolvedValue(result({ bumped_job_ids: [11, 12] }));
    api.fetchJob.mockImplementation(async (id: number) => ({ title: id === 11 ? 'Gutter' : 'Filter swap' }));
    await mount();
    expect(host.textContent).toContain('These 2 jobs go back to the queue');
    expect(host.textContent).toContain('Gutter');
    expect(host.textContent).toContain('Filter swap');
    expect(button().textContent).toBe('Force assign and return 2 to the queue');
  });

  it('warns that the job will be late when nothing can be moved', async () => {
    api.forceAssignJob.mockResolvedValue(result({ slack_minutes: -35.2, sla_label: 'breach' }));
    await mount();
    expect(host.textContent).toContain('36 min after the deadline');
    expect(host.textContent).toContain('Nothing this technician has can be moved');
  });

  it('confirming sends the real request and reports the fresh job', async () => {
    api.forceAssignJob.mockResolvedValueOnce(result());
    await mount();
    api.forceAssignJob.mockResolvedValueOnce(result({ dry_run: false }));
    await act(async () => button().click());
    expect(api.forceAssignJob).toHaveBeenLastCalledWith(9, 4, 3);
    expect(onChanged).toHaveBeenCalledWith(job);
  });

  it('shows the server message when the preview is refused', async () => {
    const { ApiError } = await import('../../shared/api/http');
    api.forceAssignJob.mockRejectedValue(new ApiError(409, { detail: 'Force-assign is for urgent jobs.' }));
    await mount();
    expect(host.querySelector('[role=alert]')?.textContent).toContain('for urgent jobs');
    expect(host.querySelector('button')).toBeNull();
  });
});
