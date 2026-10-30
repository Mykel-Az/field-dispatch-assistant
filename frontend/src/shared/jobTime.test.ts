import { describe, expect, it } from 'vitest';
import { formatSlot, formatStamp, placeLine, splitLocal, toIso, zoneAbbreviation } from './jobTime';

const CHI = 'America/Chicago';

describe('slot times on the organization clock', () => {
  it('converts local wall time to UTC, standard and daylight saving', () => {
    expect(toIso('2026-11-02', '20:00', CHI)).toBe('2026-11-03T02:00:00.000Z'); // CST, UTC-6
    expect(toIso('2026-07-01', '09:00', CHI)).toBe('2026-07-01T14:00:00.000Z'); // CDT, UTC-5
    expect(toIso('2026-07-01', '09:00', 'America/Phoenix')).toBe('2026-07-01T16:00:00.000Z'); // no DST
    expect(toIso('2026-11-02', '09:00', 'Pacific/Honolulu')).toBe('2026-11-02T19:00:00.000Z');
  });

  it('round-trips through the API format in every US zone', () => {
    for (const tz of ['America/New_York', CHI, 'America/Denver', 'America/Phoenix', 'America/Los_Angeles', 'America/Anchorage', 'Pacific/Honolulu']) {
      for (const [d, t] of [['2026-11-02', '09:30'], ['2026-12-31', '23:45'], ['2026-03-08', '12:00'], ['2026-11-01', '00:15']]) {
        expect(splitLocal(toIso(d, t, tz), tz)).toEqual({ date: d, time: t });
      }
    }
  });

  it('puts an evening slot on the organization day, not the UTC day', () => {
    expect(splitLocal('2026-11-03T02:00:00Z', CHI)).toEqual({ date: '2026-11-02', time: '20:00' });
  });

  it('is independent of the viewer machine zone', () => {
    // 09:00 Central reads 09:00 here whatever zone the test machine is in.
    expect(formatSlot(toIso('2026-11-02', '09:00', CHI), toIso('2026-11-02', '11:00', CHI), CHI)).toBe('Mon 09:00–11:00');
  });

  it('spells out both days when a slot crosses midnight', () => {
    const text = formatSlot(toIso('2026-11-02', '23:00', CHI), toIso('2026-11-03', '01:00', CHI), CHI);
    expect(text).toContain(' – ');
    expect(text).toContain('23:00');
    expect(text).toContain('01:00');
  });

  it('handles urgent jobs, which have no window', () => {
    expect(formatSlot(null, null)).toBe('No time window');
  });

  it('formats history stamps on the same clock', () => {
    expect(formatStamp('2026-11-03T02:05:00Z', CHI)).toBe('Nov 2, 20:05');
  });

  it('names the zone and follows daylight saving', () => {
    expect(zoneAbbreviation(CHI, new Date('2026-07-01T12:00:00Z'))).toBe('CDT');
    expect(zoneAbbreviation(CHI, new Date('2026-12-01T12:00:00Z'))).toBe('CST');
  });

  it('does not repeat the street on the second address line', () => {
    const base = { address: '1204 Congress Ave', postal_code: '78701' };
    expect(placeLine({ ...base, location_label: '1204 Congress Ave, 78701' })).toBe('78701');
    expect(placeLine({ ...base, location_label: 'Congress Ave, Downtown, Austin, TX' })).toBe('Congress Ave, Downtown, Austin, TX');
    expect(placeLine({ ...base, location_label: '' })).toBe('78701');
  });
});
