// Date and time helpers for job slots.
//
// Every time on screen is on the ORGANIZATION's clock (a US time zone chosen by
// the head dispatcher), not the viewer's: a dispatcher travelling, or on a
// laptop set to another zone, still sees and enters the times the job site has.
// The API speaks ISO date-times in UTC; the server derives each job's
// scheduled_date from the same zone.

const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
let zone = browserZone;
const listeners = new Set<() => void>();

/** Set the organization's zone without telling anyone (use while rendering). */
export function initOrgTimezone(tz: string) {
  zone = tz;
}
/** Change the zone and tell subscribers (use from event handlers). */
export function setOrgTimezone(tz: string) {
  if (tz === zone) return;
  zone = tz;
  listeners.forEach((l) => l());
}
export const getOrgTimezone = () => zone;
export function subscribeOrgTimezone(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const pad = (n: number) => String(n).padStart(2, '0');
const formatters = new Map<string, Intl.DateTimeFormat>();
function fmt(tz: string, key: string, options: Intl.DateTimeFormatOptions) {
  const id = `${tz}|${key}`;
  let f = formatters.get(id);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', { timeZone: tz, ...options });
    formatters.set(id, f);
  }
  return f;
}

interface Wall {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
}
/** The wall-clock reading of an instant in `tz`. */
function wall(ms: number, tz: string): Wall {
  const parts = fmt(tz, 'wall', {
    year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', hourCycle: 'h23',
  }).formatToParts(new Date(ms));
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return { year: get('year'), month: get('month'), day: get('day'), hour: get('hour') % 24, minute: get('minute') };
}
const asUtcMs = (w: Wall) => Date.UTC(w.year, w.month - 1, w.day, w.hour, w.minute);

/** "2026-11-02" + "09:00" on the org's clock -> ISO string in UTC. */
export function toIso(date: string, time: string, tz: string = zone): string {
  const [y, m, d] = date.split('-').map(Number);
  const [hh, mm] = time.split(':').map(Number);
  const guess = Date.UTC(y, m - 1, d, hh, mm);
  // The zone's offset depends on the instant itself (daylight saving), so settle in two passes.
  let result = guess - (asUtcMs(wall(guess, tz)) - guess);
  result = guess - (asUtcMs(wall(result, tz)) - result);
  return new Date(result).toISOString();
}

/** ISO string -> the org-clock date ("YYYY-MM-DD") and time ("HH:MM") for form inputs. */
export function splitLocal(iso: string, tz: string = zone): { date: string; time: string } {
  const w = wall(new Date(iso).getTime(), tz);
  return { date: `${w.year}-${pad(w.month)}-${pad(w.day)}`, time: `${pad(w.hour)}:${pad(w.minute)}` };
}

const dayKey = (iso: string, tz: string) => splitLocal(iso, tz).date;
const weekday = (d: Date, tz: string) => fmt(tz, 'wd', { weekday: 'short' }).format(d);
const dayMonth = (d: Date, tz: string) => fmt(tz, 'dm', { weekday: 'short', day: 'numeric', month: 'short' }).format(d);
const clock = (iso: string, tz: string) => splitLocal(iso, tz).time;

/** "Mon 09:00–11:00", or both ends spelled out when the slot spans days. */
export function formatSlot(start: string | null, end: string | null, tz: string = zone): string {
  if (!start || !end) return 'No time window';
  const a = new Date(start);
  const b = new Date(end);
  if (dayKey(start, tz) === dayKey(end, tz)) {
    return `${weekday(a, tz)} ${clock(start, tz)}–${clock(end, tz)}`;
  }
  return `${dayMonth(a, tz)} ${clock(start, tz)} – ${dayMonth(b, tz)} ${clock(end, tz)}`;
}

/** "Nov 2, 09:14" for the history list. */
export const formatStamp = (iso: string, tz: string = zone) =>
  `${fmt(tz, 'md', { month: 'short', day: 'numeric' }).format(new Date(iso))}, ${clock(iso, tz)}`;

/** "CST" / "CDT" (depends on the date) for the org's zone. */
export function zoneAbbreviation(tz: string = zone, at: Date = new Date()): string {
  return fmt(tz, 'abbr', { timeZoneName: 'short' }).formatToParts(at).find((p) => p.type === 'timeZoneName')?.value ?? tz;
}

/** Second address line: the geocoder's label, unless it only repeats the street. */
export function placeLine(job: { address: string; location_label?: string | null; postal_code: string }): string {
  const label = job.location_label?.trim();
  return label && !label.toLowerCase().startsWith(job.address.trim().toLowerCase()) ? label : job.postal_code;
}
