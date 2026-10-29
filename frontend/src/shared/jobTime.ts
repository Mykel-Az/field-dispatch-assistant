// Date and time helpers for job slots. The API speaks ISO date-times; people
// enter a date plus clock times in their own timezone.
//
// TIME: slots are interpreted in the browser's timezone and the server derives
// scheduled_date in UTC. Full-fidelity path: an Organization timezone used by
// both sides, so a 00:30 local slot lands on the right day.

/** "2026-11-02" + "09:00" (local) -> ISO string in UTC. */
export function toIso(date: string, time: string): string {
  return new Date(`${date}T${time}`).toISOString();
}

const pad = (n: number) => String(n).padStart(2, '0');

/** ISO string -> the local date ("YYYY-MM-DD") and time ("HH:MM") for form inputs. */
export function splitLocal(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'short' });
const dayMonth = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
const stamp = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

/** "Mon 09:00–11:00", or both ends spelled out when the slot spans days. */
export function formatSlot(start: string | null, end: string | null): string {
  if (!start || !end) return 'No time window';
  const a = new Date(start);
  const b = new Date(end);
  if (a.toDateString() === b.toDateString()) {
    return `${weekday.format(a)} ${clock.format(a)}–${clock.format(b)}`;
  }
  return `${dayMonth.format(a)} ${clock.format(a)} – ${dayMonth.format(b)} ${clock.format(b)}`;
}

/** "2 Nov, 09:14" for the history list. */
export const formatStamp = (iso: string) => stamp.format(new Date(iso));

/** Second address line: the geocoder's label, unless it only repeats the street. */
export function placeLine(job: { address: string; location_label?: string | null; postal_code: string }): string {
  const label = job.location_label?.trim();
  return label && !label.toLowerCase().startsWith(job.address.trim().toLowerCase()) ? label : job.postal_code;
}
