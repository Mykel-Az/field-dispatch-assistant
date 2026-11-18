import { describe, expect, it } from 'vitest';
import type { TechnicianJob } from '../shared/api/models';
import { afterAction, currentJobId, directionsUrl, progress, telHref } from './jobsModel';

const job = (id: number, status: string, over: Partial<TechnicianJob> = {}) =>
  ({ id, status, lat: 30.2, lng: -97.7, address: '1 Main St', postal_code: '78701', ...over }) as TechnicianJob;

describe('currentJobId', () => {
  it('is the job in progress, even when an earlier stop is still waiting', () => {
    expect(currentJobId([job(1, 'assigned'), job(2, 'ongoing')])).toBe(2);
  });
  it('is the first waiting job when nothing is in progress', () => {
    expect(currentJobId([job(1, 'completed'), job(2, 'assigned'), job(3, 'assigned')])).toBe(2);
  });
  it('is null when everything is done or the day is empty', () => {
    expect(currentJobId([job(1, 'completed')])).toBeNull();
    expect(currentJobId([])).toBeNull();
  });
});

describe('progress', () => {
  it('counts completed jobs out of all of today’s', () => {
    expect(progress([job(1, 'completed'), job(2, 'ongoing'), job(3, 'assigned')])).toEqual({ done: 1, total: 3 });
  });
});

describe('afterAction', () => {
  it('swaps in the server’s version of the job', () => {
    const next = afterAction([job(1, 'assigned'), job(2, 'assigned')], job(1, 'ongoing'));
    expect(next.map((j) => j.status)).toEqual(['ongoing', 'assigned']);
  });
  it('drops a job that went back to the queue', () => {
    expect(afterAction([job(1, 'ongoing'), job(2, 'assigned')], job(1, 'unassigned')).map((j) => j.id)).toEqual([2]);
  });
});

describe('links', () => {
  it('directions use the pin when the job has one, and the address otherwise', () => {
    expect(directionsUrl(job(1, 'assigned'))).toContain('destination=30.2%2C-97.7');
    expect(directionsUrl(job(1, 'assigned', { lat: null, lng: null }))).toContain('1%20Main%20St%2078701');
  });
  it('a phone number keeps only digits and a leading plus', () => {
    expect(telHref('(512) 555-0100')).toBe('tel:5125550100');
    expect(telHref('+1 512 555 0100')).toBe('tel:+15125550100');
  });
});
