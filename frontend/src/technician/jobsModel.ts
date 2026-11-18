import type { TechnicianJob } from '../shared/api/models';

/** The job to work on now: the one in progress, otherwise the next one in the order. */
export function currentJobId(jobs: TechnicianJob[]): number | null {
  const ongoing = jobs.find((j) => j.status === 'ongoing');
  if (ongoing) return ongoing.id;
  return jobs.find((j) => j.status === 'assigned')?.id ?? null;
}

export function progress(jobs: TechnicianJob[]): { done: number; total: number } {
  return { done: jobs.filter((j) => j.status === 'completed').length, total: jobs.length };
}

/** The list after an action: the job as the server now has it, or gone when it left my list. */
export function afterAction(jobs: TechnicianJob[], updated: TechnicianJob): TechnicianJob[] {
  if (updated.status === 'unassigned') return jobs.filter((j) => j.id !== updated.id);
  return jobs.map((j) => (j.id === updated.id ? updated : j));
}

/** Directions in whatever maps app the phone opens: the pin when there is one, else the address. */
export function directionsUrl(job: Pick<TechnicianJob, 'lat' | 'lng' | 'address' | 'postal_code'>): string {
  const destination =
    job.lat != null && job.lng != null ? `${job.lat},${job.lng}` : `${job.address} ${job.postal_code}`;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
}

/** `tel:` link for a phone number typed any way ("(512) 555-0100"). */
export function telHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, '')}`;
}
