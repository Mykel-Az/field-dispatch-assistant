import { Link } from 'react-router-dom';
import type { JobRow, ScheduleResult, Technician } from '../../shared/api/models';
import { ui } from '../../shared/ui';
import {
  arrivalTime,
  groupByTechnician,
  hasSla,
  rejectionLines,
  slackText,
  slaMeta,
  summaryLine,
} from './planModel';

interface Props {
  result: ScheduleResult;
  technicians: Technician[];
  /** Job rows for the planned day, to show titles. A missing job falls back to "Job #id". */
  jobs: Map<number, JobRow>;
  /** The organization's time zone; omit to use the one set for the app. */
  timezone?: string;
}

const titleOf = (jobs: Map<number, JobRow>, id: number) => jobs.get(id)?.title ?? `Job #${id}`;

function Why({ lines }: { lines: string[] }) {
  if (lines.length === 0) return null;
  return (
    <details className="mt-2 text-sm text-ink-muted">
      <summary className="cursor-pointer font-medium">Why not the others?</summary>
      <ul className="mt-1 list-disc pl-5">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </details>
  );
}

export default function PlanResults({ result, technicians, jobs, timezone }: Props) {
  const plans = groupByTechnician(result.assigned, technicians);
  const empty =
    result.assigned.length === 0 && result.unassigned.length === 0 && result.skipped.length === 0;

  if (empty) {
    return (
      <p className={ui.muted}>
        Nothing to plan for this day: there are no unassigned jobs.{' '}
        <Link
          className="font-semibold text-brand-ink underline"
          to={`/jobs?scheduled_date=${result.plan_date}`}
        >
          See this day’s jobs
        </Link>
      </p>
    );
  }

  return (
    <div className="grid gap-6">
      <p role="status" className="font-semibold">
        {summaryLine({
          assigned: result.assigned.length,
          technicians: plans.length,
          unassigned: result.unassigned.length,
          skipped: result.skipped.length,
        })}
      </p>

      {plans.map((plan) => (
        <section key={plan.technicianId} aria-label={plan.name}>
          <h3 className="mb-2 flex flex-wrap items-baseline gap-x-3 text-lg font-bold">
            {plan.name}
            <span className="text-sm font-normal text-ink-muted">
              {plan.shift && `${plan.shift} · `}
              {plan.stops.length} job{plan.stops.length === 1 ? '' : 's'}
            </span>
          </h3>
          <ol className="grid gap-3">
            {plan.stops.map((stop) => {
              const sla = slaMeta(stop.sla_label);
              return (
                <li key={stop.job_id} className="rounded-xl border border-line bg-surface p-4">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="text-lg font-bold tabular-nums">
                      {arrivalTime(stop.estimated_arrival, timezone)}
                    </span>
                    <Link
                      className="font-semibold text-brand-ink underline"
                      to={`/jobs/${stop.job_id}`}
                    >
                      {titleOf(jobs, stop.job_id)}
                    </Link>
                    {hasSla(stop.sla_label) && (
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-0.5 text-sm font-bold ${sla.classes}`}
                      >
                        <span aria-hidden="true">{sla.mark}</span>
                        {sla.label} · {slackText(stop.slack_minutes)}
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-sm">{stop.sentence}</p>
                  <Why lines={rejectionLines(stop.reasons, technicians)} />
                </li>
              );
            })}
          </ol>
        </section>
      ))}

      {result.unassigned.length > 0 && (
        <section aria-label="Could not be assigned">
          <h3 className="mb-2 text-lg font-bold">Could not be assigned</h3>
          <ul className="grid gap-3">
            {result.unassigned.map((job) => (
              <li key={job.job_id} className="rounded-xl border border-warn-ink/30 bg-warn-soft p-4">
                <Link className="font-semibold text-warn-ink underline" to={`/jobs/${job.job_id}`}>
                  {titleOf(jobs, job.job_id)}
                </Link>
                <p className="mt-1 text-sm text-warn-ink">{job.sentence}</p>
                <Why lines={rejectionLines(job.reasons, technicians)} />
                <Link
                  className={`${ui.btnSmall} mt-3 inline-flex items-center`}
                  to={`/jobs/${job.job_id}`}
                >
                  Assign by hand
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.skipped.length > 0 && (
        <section aria-label="Need a location">
          <h3 className="mb-2 text-lg font-bold">Need a location first</h3>
          <ul className="grid gap-3">
            {result.skipped.map((job) => (
              <li key={job.job_id} className="rounded-xl border border-line bg-surface p-4">
                <Link className="font-semibold text-brand-ink underline" to={`/jobs/${job.job_id}`}>
                  {titleOf(jobs, job.job_id)}
                </Link>
                <p className="mt-1 text-sm text-ink-muted">{job.sentence}</p>
                <Link
                  className={`${ui.btnSmall} mt-3 inline-flex items-center`}
                  to={`/jobs/${job.job_id}`}
                >
                  Fix the location
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}