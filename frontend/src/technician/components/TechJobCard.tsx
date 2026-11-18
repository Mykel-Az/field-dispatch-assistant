import type { TechnicianJob } from '../../shared/api/models';
import JobTags from '../../shared/components/JobTags';
import StatusBadge from '../../shared/components/StatusBadge';
import { formatWhen, placeLine, splitLocal } from '../../shared/jobTime';
import { ui } from '../../shared/ui';
import { directionsUrl, telHref } from '../jobsModel';

export type Action = 'arrive' | 'complete' | 'incomplete';

interface Props {
  job: TechnicianJob;
  stop: number;
  /** The job to work on now: it gets the three large buttons and a stronger border. */
  current: boolean;
  /** Another job is in progress, so this one cannot be started yet. */
  blocked: boolean;
  /** An action is being sent: every button waits. */
  busy: boolean;
  onAction: (job: TechnicianJob, action: Action) => void;
}

const BIG = 'min-h-14 w-full text-lg';

export default function TechJobCard({ job, stop, current, blocked, busy, onAction }: Props) {
  const ongoing = job.status === 'ongoing';
  const done = job.status === 'completed';
  return (
    <article
      id={`job-${job.id}`}
      aria-current={current ? 'step' : undefined}
      className={`rounded-card border bg-surface p-4 shadow-sm ${current ? 'border-brand ring-2 ring-brand/30' : 'border-line'} ${done ? 'opacity-75' : ''}`}
    >
      <div className="flex items-start gap-3">
        <span
          aria-label={`Stop ${stop}`}
          className="grid size-9 shrink-0 place-items-center rounded-full bg-brand text-sm font-bold text-on-brand"
        >
          {stop}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="break-words text-lg font-bold leading-snug">{job.title}</h2>
          <p className="mt-0.5 text-sm font-semibold">
            {job.is_urgent && !job.slot_start ? 'As soon as possible' : formatWhen(job)}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <StatusBadge status={job.status} />
            {job.is_urgent && <span className="rounded-full bg-danger-soft px-2.5 py-0.5 text-xs font-bold text-danger">Urgent</span>}
            <JobTags job={job} />
          </div>
        </div>
      </div>

      <dl className="mt-3 grid gap-1.5 text-sm">
        <div>
          <dt className="sr-only">Customer</dt>
          <dd className="font-medium">{job.customer_name}</dd>
        </div>
        <div>
          <dt className="sr-only">Address</dt>
          <dd>
            {job.address}
            <span className="block text-ink-muted">{placeLine(job)}</span>
          </dd>
        </div>
        {job.description && (
          <div>
            <dt className="sr-only">Notes</dt>
            <dd className="text-ink-muted">{job.description}</dd>
          </div>
        )}
        {job.estimated_arrival && !done && (
          <div className="text-ink-muted">Planned arrival {splitLocal(job.estimated_arrival).time}</div>
        )}
        {done && job.completed_at && (
          <div className="text-ink-muted">Finished {splitLocal(job.completed_at).time}</div>
        )}
      </dl>

      {!done && (
        <div className="mt-3 flex flex-wrap gap-2">
          <a className={`${ui.btnSmall} inline-flex items-center`} href={directionsUrl(job)} target="_blank" rel="noopener noreferrer">
            Directions
          </a>
          {job.customer_phone && (
            <a className={`${ui.btnSmall} inline-flex items-center`} href={telHref(job.customer_phone)}>
              Call {job.customer_phone}
            </a>
          )}
        </div>
      )}

      {current && (
        <div className="mt-4 grid gap-2" role="group" aria-label="Job actions">
          <button className={`${ui.btn} ${BIG}`} disabled={busy || ongoing || blocked} onClick={() => onAction(job, 'arrive')}>
            Arrive
          </button>
          <button className={`${ui.btn} ${BIG}`} disabled={busy || !ongoing} onClick={() => onAction(job, 'complete')}>
            Complete
          </button>
          <button className={`${ui.btnDanger} ${BIG}`} disabled={busy || !ongoing} onClick={() => onAction(job, 'incomplete')}>
            Couldn’t finish
          </button>
        </div>
      )}

      {!current && job.status === 'assigned' && (
        <div className="mt-3">
          <button className={`${ui.btnSmall} min-h-12 w-full`} disabled={busy || blocked} onClick={() => onAction(job, 'arrive')}>
            Arrive here instead
          </button>
          {blocked && <p className={`${ui.muted} mt-1`}>Finish your current job first.</p>}
        </div>
      )}
    </article>
  );
}
