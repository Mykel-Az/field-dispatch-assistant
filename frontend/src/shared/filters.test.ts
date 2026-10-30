import { describe, expect, it } from 'vitest';
import { filterQuery, hasFilters, NO_FILTERS, readFilters, toggleStatus, toggleTechnician, writeFilters } from './filters';

describe('job filters', () => {
  it('reads repeated statuses and ignores unknown ones', () => {
    const f = readFilters(new URLSearchParams('status=assigned&status=nope&status=ongoing&technician=7&technician=9&technician=x'));
    expect(f.statuses).toEqual(['assigned', 'ongoing']);
    expect(f.technicians).toEqual(['7', '9']);
  });

  it('writes one status param per status and keeps unrelated keys', () => {
    const next = writeFilters(new URLSearchParams('page=3&status=failed'), {
      statuses: ['assigned', 'ongoing'],
      date: '2026-11-02',
      technicians: ['3', '5'],
    });
    expect(next.getAll('status')).toEqual(['assigned', 'ongoing']);
    expect(next.get('scheduled_date')).toBe('2026-11-02');
    expect(next.get('page')).toBe('3');
    expect(next.getAll('technician')).toEqual(['3', '5']);
  });

  it('builds an empty query for no filters', () => {
    expect(filterQuery(NO_FILTERS).toString()).toBe('');
    expect(hasFilters(NO_FILTERS)).toBe(false);
  });

  it('toggles technicians on and off', () => {
    const on = toggleTechnician(NO_FILTERS, '4');
    expect(on.technicians).toEqual(['4']);
    expect(toggleTechnician(toggleTechnician(on, '6'), '4').technicians).toEqual(['6']);
  });

  it('toggles a status on and off', () => {
    const on = toggleStatus(NO_FILTERS, 'failed');
    expect(on.statuses).toEqual(['failed']);
    expect(toggleStatus(on, 'failed').statuses).toEqual([]);
  });
});
