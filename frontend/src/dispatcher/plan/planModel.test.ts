import { describe, expect, it } from 'vitest';
import type { PlannedJob, Technician } from '../../shared/api/models';
import {
  addDays,
  arrivalTime,
  groupByTechnician,
  rejectionLines,
  slackText,
  slaMeta,
  summaryLine,
  todayOnClock,
} from './planModel';

const tech = (id: number, name: string, start = '08:00:00', end = '17:00:00'): Technician =>
  ({
    id,
    user: { id: id + 100, full_name: name },
    skills: [],
    shift_start: start,
    shift_end: end,
    phone: null,
  }) as unknown as Technician;

const stop = (job_id: number, technician_id: number, estimated_arrival: string): PlannedJob => ({
  job_id,
  placed_by: 'planner',
  technician_id,
  estimated_arrival,
  sla_label: 'ok',
  slack_minutes: 30,
  reasons: [],
  sentence: '',
});

describe('groupByTechnician', () => {
  const techs = [tech(2, 'Sam'), tech(1, 'Alex', '09:00:00', '18:00:00')];

  it('groups by technician, people A to Z, stops in arrival order', () => {
    const plans = groupByTechnician(
      [
        stop(10, 2, '2026-11-02T20:00:00Z'),
        stop(11, 1, '2026-11-02T16:00:00Z'),
        stop(12, 2, '2026-11-02T15:00:00Z'),
      ],
      techs,
    );
    expect(plans.map((p) => p.name)).toEqual(['Alex', 'Sam']);
    expect(plans[1].stops.map((s) => s.job_id)).toEqual([12, 10]);
  });

  it('shows the shift without seconds', () => {
    const [alex] = groupByTechnician([stop(1, 1, '2026-11-02T16:00:00Z')], techs);
    expect(alex.shift).toBe('09:00–18:00');
  });

  it('copes with a technician that is not in the loaded list', () => {
    const [plan] = groupByTechnician([stop(1, 99, '2026-11-02T16:00:00Z')], techs);
    expect(plan.name).toBe('Technician #99');
    expect(plan.shift).toBe('');
  });

  it('returns nothing for nothing', () => {
    expect(groupByTechnician([], techs)).toEqual([]);
  });
});

describe('slackText', () => {
  it.each([
    [48.9, '48 min to spare'],
    [0, '0 min to spare'],
    [-6.2, '7 min late'],
    [-0.5, '1 min late'],
  ])('%f -> %s', (slack, text) => expect(slackText(slack)).toBe(text));
});

describe('slaMeta', () => {
  it('names each label in words as well as colour', () => {
    expect(slaMeta('ok').label).toBe('On time');
    expect(slaMeta('at_risk').label).toBe('At risk');
    expect(slaMeta('breach').label).toBe('Late');
  });
  it('does not crash on a label it does not know', () => {
    expect(slaMeta('mystery').label).toBe('mystery');
  });
});

describe('summaryLine', () => {
  it('joins only the parts that exist', () => {
    expect(summaryLine({ assigned: 5, technicians: 3, unassigned: 2, skipped: 1 })).toBe(
      'Planned 5 jobs across 3 technicians · 2 jobs could not be assigned · 1 job needs a location',
    );
  });
  it('says "need" for several jobs without a location', () => {
    expect(summaryLine({ assigned: 0, technicians: 0, unassigned: 0, skipped: 2 })).toBe(
      '2 jobs need a location',
    );
  });
  it('uses singular forms', () => {
    expect(summaryLine({ assigned: 1, technicians: 1, unassigned: 0, skipped: 0 })).toBe(
      'Planned 1 job across 1 technician',
    );
  });
});

describe('rejectionLines', () => {
  const techs = [tech(1, 'Alex'), tech(2, 'Sam'), tech(3, 'Jo')];
  it('names each technician that was passed over and why', () => {
    const lines = rejectionLines(
      [
        { code: 'assigned', facts: { technician_id: 1 } },
        { code: 'unavailable', facts: { technician_id: 2 } },
        { code: 'daily_limit', facts: { technician_id: 3, limit: 4, assigned_count: 4 } },
        { code: 'skill_mismatch', facts: { technician_id: 9 } },
        { code: 'after_closing', facts: { technician_id: 1, minutes_after_closing: 7 } },
      ],
      techs,
    );
    expect(lines).toEqual([
      'Sam is unavailable',
      'Jo has reached the daily limit of 4 jobs',
      'Technician #9 does not have a matching skill',
      'Alex would arrive 7 min after closing',
    ]);
  });
  it('has nothing to say when nobody was passed over', () => {
    expect(rejectionLines([{ code: 'assigned', facts: { technician_id: 1 } }], techs)).toEqual([]);
  });
});

describe('dates', () => {
  it('adds days across a month end', () => {
    expect(addDays('2026-11-28', 5)).toBe('2026-12-03');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
  });
  it('takes today from the organization clock, not the browser clock', () => {
    const lateInLagos = new Date('2026-11-03T03:00:00Z'); // still 2 Nov in Chicago
    expect(todayOnClock('America/Chicago', lateInLagos)).toBe('2026-11-02');
    expect(todayOnClock('Pacific/Auckland', lateInLagos)).toBe('2026-11-03');
  });
  it('shows arrivals on the organization clock', () => {
    expect(arrivalTime('2026-11-02T15:12:00Z', 'America/Chicago')).toBe('09:12');
  });
});
