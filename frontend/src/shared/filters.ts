// Job filters shared by the Jobs list and the Map. They live in the URL, so a
// filtered view can be bookmarked, shared and survives a reload.
//   ?status=assigned&status=ongoing&scheduled_date=2026-11-02&technician=7&technician=9
import { isJobStatus, type JobStatus } from './status';

export interface JobFilterValues {
  /** Empty means "every status". */
  statuses: JobStatus[];
  date: string;
  /** Technician ids. Empty means everyone. */
  technicians: string[];
}

export const NO_FILTERS: JobFilterValues = { statuses: [], date: '', technicians: [] };

export function readFilters(params: URLSearchParams): JobFilterValues {
  return {
    statuses: params.getAll('status').filter(isJobStatus),
    date: params.get('scheduled_date') ?? '',
    technicians: params.getAll('technician').filter((t) => /^\d+$/.test(t)),
  };
}

/** Writes the filters into `params` (leaving other keys, like `page`, alone). */
export function writeFilters(params: URLSearchParams, f: JobFilterValues): URLSearchParams {
  const next = new URLSearchParams(params);
  next.delete('status');
  f.statuses.forEach((s) => next.append('status', s));
  if (f.date) next.set('scheduled_date', f.date);
  else next.delete('scheduled_date');
  next.delete('technician');
  f.technicians.forEach((t) => next.append('technician', t));
  return next;
}

/** The API query string for these filters ('' when none). */
export function filterQuery(f: JobFilterValues): URLSearchParams {
  return writeFilters(new URLSearchParams(), f);
}

export const hasFilters = (f: JobFilterValues) =>
  f.statuses.length > 0 || f.date !== '' || f.technicians.length > 0;

export function toggleStatus(f: JobFilterValues, s: JobStatus): JobFilterValues {
  const on = f.statuses.includes(s);
  return { ...f, statuses: on ? f.statuses.filter((x) => x !== s) : [...f.statuses, s] };
}

export function toggleTechnician(f: JobFilterValues, id: string): JobFilterValues {
  const on = f.technicians.includes(id);
  return { ...f, technicians: on ? f.technicians.filter((x) => x !== id) : [...f.technicians, id] };
}
