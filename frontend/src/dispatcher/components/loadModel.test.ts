import { describe, expect, it } from 'vitest';
import type { MapPin } from '../../shared/api/client';
import { countByTechnician, limitWarning, loadText } from './loadModel';

const pin = (id: number, technician_id: number | null, status: string): MapPin => ({
  id, lat: 1, lng: 1, status, technician_id, is_urgent: false,
});

describe('countByTechnician', () => {
  it('counts assigned and ongoing jobs per technician, and nothing else', () => {
    const counts = countByTechnician([
      pin(1, 7, 'assigned'), pin(2, 7, 'ongoing'), pin(3, 7, 'completed'),
      pin(4, 9, 'assigned'), pin(5, null, 'unassigned'), pin(6, 9, 'canceled'),
    ]);
    expect(counts.get(7)).toBe(2);
    expect(counts.get(9)).toBe(1);
    expect(counts.has(1)).toBe(false);
  });
});

describe('limitWarning', () => {
  it('is silent under the limit and when the limit is unknown', () => {
    expect(limitWarning('Sam', 2, 3, false)).toBeNull();
    expect(limitWarning('Sam', 9, null, false)).toBeNull();
  });
  it('warns at the limit and above it, without forbidding', () => {
    expect(limitWarning('Sam', 3, 3, false)).toBe(
      'Sam already has 3 jobs that day (limit 3). You can still assign this job; the planner would not.',
    );
    expect(limitWarning('Sam', 5, 3, false)).toContain('5 jobs');
  });
  it('says urgent jobs may go over the limit', () => {
    expect(limitWarning('Sam', 3, 3, true)).toContain('urgent');
  });
  it('uses the singular for one job', () => {
    expect(limitWarning('Sam', 1, 1, false)).toContain('1 job that day');
  });
});

describe('loadText', () => {
  it('shows the limit when known', () => {
    expect(loadText(2, 3)).toBe('2 jobs that day (limit 3)');
    expect(loadText(0, null)).toBe('0 jobs that day');
  });
});
