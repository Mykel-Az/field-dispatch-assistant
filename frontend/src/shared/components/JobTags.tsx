import type { JobRow } from '../api/models';

type Tagged = Pick<JobRow, 'priority' | 'slot_is_fixed'>;

const PILL = 'rounded-full px-2.5 py-0.5 text-xs font-bold';

/**
 * Small labels for what is unusual about a job: a high or low priority, and a day
 * with no agreed time. A normal job with a fixed window shows nothing, so the tags
 * mean something when they do appear.
 */
export default function JobTags({ job, className = '' }: { job: Tagged | undefined; className?: string }) {
  if (!job) return null;
  const high = job.priority === 'high';
  const low = job.priority === 'low';
  const anytime = job.slot_is_fixed === false;
  if (!high && !low && !anytime) return null;
  return (
    <span className={`inline-flex flex-wrap items-center gap-1.5 align-middle ${className}`}>
      {high && <span className={`${PILL} bg-warn-soft text-warn-ink`}>High priority</span>}
      {low && <span className={`${PILL} bg-canvas text-ink-muted ring-1 ring-line`}>Low priority</span>}
      {anytime && <span className={`${PILL} bg-brand-soft text-brand-ink`}>Any time</span>}
    </span>
  );
}
