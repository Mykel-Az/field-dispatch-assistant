import { describe, expect, it } from 'vitest';
import { backLabel } from './useBack';

describe('backLabel', () => {
  it('names the page the person came from', () => {
    expect(backLabel({ back: 'plan' }, true)).toBe('← Back to plan');
    expect(backLabel({ back: 'map' }, true)).toBe('← Back to map');
    expect(backLabel({ back: 'jobs' }, true)).toBe('← Back to jobs');
  });
  it('says plain Back when there is history but no named origin', () => {
    expect(backLabel(null, true)).toBe('← Back');
    expect(backLabel({ back: 'elsewhere' }, true)).toBe('← Back');
  });
  it('falls back to the jobs list when opened directly', () => {
    expect(backLabel(null, false)).toBe('← All jobs');
  });
});
