import { describe, expect, it } from 'vitest';
import { formatSlot, placeLine, splitLocal, toIso } from './jobTime';

describe('slot times', () => {
  it('round-trips a local date and time through the API format', () => {
    // True in any timezone, because both directions use the machine's zone.
    expect(splitLocal(toIso('2026-11-02', '09:30'))).toEqual({ date: '2026-11-02', time: '09:30' });
    expect(splitLocal(toIso('2026-12-31', '23:45'))).toEqual({ date: '2026-12-31', time: '23:45' });
  });

  it('sends an ISO string the API accepts', () => {
    expect(toIso('2026-11-02', '09:00')).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });

  it('shows one line for a same-day slot', () => {
    const text = formatSlot(toIso('2026-11-02', '09:00'), toIso('2026-11-02', '11:00'));
    expect(text).toMatch(/^\w{3} 09:00–11:00$/);
  });

  it('spells out both days when a slot crosses midnight', () => {
    const text = formatSlot(toIso('2026-11-02', '23:00'), toIso('2026-11-03', '01:00'));
    expect(text).toContain(' – ');
    expect(text).toContain('23:00');
    expect(text).toContain('01:00');
  });

  it('handles urgent jobs, which have no window', () => {
    expect(formatSlot(null, null)).toBe('No time window');
  });

  it('does not repeat the street on the second address line', () => {
    const base = { address: '1204 Congress Ave', postal_code: '78701' };
    expect(placeLine({ ...base, location_label: '1204 Congress Ave, 78701' })).toBe('78701');
    expect(placeLine({ ...base, location_label: 'Congress Ave, Downtown, Austin, TX' })).toBe('Congress Ave, Downtown, Austin, TX');
    expect(placeLine({ ...base, location_label: '' })).toBe('78701');
  });
});
