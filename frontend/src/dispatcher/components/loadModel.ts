import type { MapPin } from '../../shared/api/client';

/** Jobs already on each technician's day: pins that are assigned or underway. */
export function countByTechnician(pins: MapPin[]): Map<number, number> {
  const counts = new Map<number, number>();
  for (const pin of pins) {
    if (pin.technician_id === null) continue;
    if (pin.status !== 'assigned' && pin.status !== 'ongoing') continue;
    counts.set(pin.technician_id, (counts.get(pin.technician_id) ?? 0) + 1);
  }
  return counts;
}

const plural = (n: number) => `${n} ${n === 1 ? 'job' : 'jobs'}`;

/** "3 jobs that day", with the limit once it is known. */
export function loadText(count: number, limit: number | null): string {
  return limit === null ? `${plural(count)} that day` : `${plural(count)} that day (limit ${limit})`;
}

/**
 * Shown when the dispatcher picks someone who is already at the daily limit.
 * Never blocks: assigning by hand is the dispatcher's call, the planner is the
 * one that keeps to the limit. `null` means no warning is needed.
 */
export function limitWarning(
  name: string,
  count: number,
  limit: number | null,
  urgent: boolean,
): string | null {
  if (limit === null || count < limit) return null;
  const lead = `${name} already has ${plural(count)} that day (limit ${limit}).`;
  return urgent
    ? `${lead} This job is urgent, which the planner allows to go over the limit.`
    : `${lead} You can still assign this job; the planner would not.`;
}
