import type { JobHistoryRow } from './api/models';

/**
 * Who a history line credits. A change the planner made says so, with the person
 * who pressed "Run plan" in brackets: "Planner (run by Dana Reyes)". A change a
 * person made on a screen is credited to them; a row with nobody is "System".
 */
export function historyActor(row: Pick<JobHistoryRow, 'source' | 'changed_by'>): string {
  const person = row.changed_by?.full_name;
  if (row.source === 'planner') return person ? `Planner (run by ${person})` : 'Planner';
  return person ?? 'System';
}
