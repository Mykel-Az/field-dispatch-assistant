import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { JobRow, ScheduleResult, Technician } from '../../shared/api/models';
import { formatWhen } from '../../shared/jobTime';
import JobTags from '../../shared/components/JobTags';
import type { LatLng } from '../../shared/map/PinMap';
import { FROM_PLAN } from '../../shared/useBack';
import { ui } from '../../shared/ui';
import {
  arrivalTime,
  groupByTechnician,
  hasSla,
  isByHand,
  rejectionLines,
  slackText,
  slaMeta,
  summaryLine,
} from './planModel';
import PlanMap from './PlanMap';
import PlanMapKey from './PlanMapKey';
import { buildPlanMap, techColor } from './planMapModel';

interface Props {
  result: ScheduleResult;
  technicians: Technician[];
  /** Job rows for the planned day, to show titles. A missing job falls back to "Job #id". */
  jobs: Map<number, JobRow>;
  /** The organization's time zone; omit to use the one set for the app. */
  timezone?: string;
  /** Where each job is, for the map. Without it the map simply has less on it. */
  locations?: Map<number, { lat: number; lng: number }>;
  /** The office, drawn on the map and where each line starts. */
  office?: LatLng | null;
}

const NO_LOCATIONS = new Map<number, { lat: number; lng: number }>();

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

const selectedCard = (selected: boolean, base: string) =>
  selected ? `${base} ring-2 ring-brand` : base;

export default function PlanResults({
  result,
  technicians,
  jobs,
  timezone,
  locations = NO_LOCATIONS,
  office = null,
}: Props) {
  const plans = useMemo(
    () =>
      groupByTechnician(result.assigned, technicians, (id) => jobs.get(id)?.slot_start),
    [result, technicians, jobs],
  );
  const mapData = useMemo(
    () =>
      buildPlanMap({
        plans,
        unassigned: result.unassigned,
        locations,
        technicians,
        office,
        titleOf: (id) => titleOf(jobs, id),
        timeOf: (stop) =>
          stop.estimated_arrival ? arrivalTime(stop.estimated_arrival, timezone) : 'by hand',
      }),
    [plans, result.unassigned, locations, technicians, office, jobs, timezone],
  );
  const showMap = mapData.routes.length > 0 || mapData.misses.length > 0;
  // One job is "selected" at a time: the marker and its card light up together.
  const [selected, setSelected] = useState<number | null>(null);
  const select = (jobId: number, fromMap = false) => {
    setSelected(jobId);
    if (fromMap) {
      const card = document.getElementById(`plan-job-${jobId}`);
      const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      card?.scrollIntoView?.({ block: 'nearest', behavior: calm ? 'auto' : 'smooth' });
    }
  };
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

  const lists = (
    <div className="grid min-w-0 gap-6">
      {plans.map((plan) => {
        const color = techColor(plan.technicianId, technicians);
        return (
          <section key={plan.technicianId} aria-label={plan.name}>
            <h3 className="mb-2 flex flex-wrap items-baseline gap-x-3 text-lg font-bold">
              {plan.name}
              <span className="text-sm font-normal text-ink-muted">
                {plan.shift && `${plan.shift} · `}
                {plan.stops.length} job{plan.stops.length === 1 ? '' : 's'}
              </span>
            </h3>
            <ol className="grid gap-3">
              {plan.stops.map((stop, i) => {
                const sla = slaMeta(stop.sla_label);
                return (
                  <li
                    key={stop.job_id}
                    id={`plan-job-${stop.job_id}`}
                    onClick={() => select(stop.job_id)}
                    className={selectedCard(
                      selected === stop.job_id,
                      'scroll-mt-4 rounded-xl border border-line bg-surface p-4',
                    )}
                  >
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span
                        aria-label={`Stop ${i + 1}`}
                        className="grid size-7 shrink-0 place-items-center rounded-full text-sm font-bold text-white"
                        style={{ background: color }}
                      >
                        {i + 1}
                      </span>
                      {stop.estimated_arrival ? (
                        <span className="text-lg font-bold tabular-nums">
                          {arrivalTime(stop.estimated_arrival, timezone)}
                        </span>
                      ) : (
                        <span className="text-sm font-semibold tabular-nums">
                          {jobs.get(stop.job_id) ? formatWhen(jobs.get(stop.job_id)!, timezone) : 'Time not set'}
                        </span>
                      )}
                      <Link
                        className="font-semibold text-brand-ink underline"
                        to={`/jobs/${stop.job_id}`}
                        state={FROM_PLAN}
                      >
                        {titleOf(jobs, stop.job_id)}
                      </Link>
                      <JobTags job={jobs.get(stop.job_id)} />
                      {isByHand(stop) && (
                        <span className="inline-flex items-center rounded-full border border-line bg-canvas px-3 py-0.5 text-sm font-semibold text-ink-muted">
                          Assigned by hand
                        </span>
                      )}
                      {hasSla(stop.sla_label) && (
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-0.5 text-sm font-bold ${sla.classes}`}
                        >
                          <span aria-hidden="true">{sla.mark}</span>
                          {sla.label} · {slackText(stop.slack_minutes)}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-sm">
                      {isByHand(stop)
                        ? 'You assigned this job. The planner works around it: new jobs are planned after it.'
                        : stop.sentence}
                    </p>
                    <Why lines={rejectionLines(stop.reasons, technicians)} />
                  </li>
                );
              })}
            </ol>
          </section>
        );
      })}

      {result.unassigned.length > 0 && (
        <section aria-label="Could not be assigned">
          <h3 className="mb-2 text-lg font-bold">Could not be assigned</h3>
          <ul className="grid gap-3">
            {result.unassigned.map((job) => (
              <li
                key={job.job_id}
                id={`plan-job-${job.job_id}`}
                onClick={() => select(job.job_id)}
                className={selectedCard(
                  selected === job.job_id,
                  'scroll-mt-4 rounded-xl border border-warn-ink/30 bg-warn-soft p-4',
                )}
              >
                <Link className="font-semibold text-warn-ink underline" to={`/jobs/${job.job_id}`} state={FROM_PLAN}>
                  {titleOf(jobs, job.job_id)}
                </Link>
                <JobTags className="ml-2" job={jobs.get(job.job_id)} />
                <p className="mt-1 text-sm text-warn-ink">{job.sentence}</p>
                <Why lines={rejectionLines(job.reasons, technicians)} />
                <Link
                  className={`${ui.btnSmall} mt-3 inline-flex items-center`}
                  to={`/jobs/${job.job_id}`}
                  state={FROM_PLAN}
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
                <Link className="font-semibold text-brand-ink underline" to={`/jobs/${job.job_id}`} state={FROM_PLAN}>
                  {titleOf(jobs, job.job_id)}
                </Link>
                <JobTags className="ml-2" job={jobs.get(job.job_id)} />
                <p className="mt-1 text-sm text-ink-muted">{job.sentence}</p>
                <Link
                  className={`${ui.btnSmall} mt-3 inline-flex items-center`}
                  to={`/jobs/${job.job_id}`}
                  state={FROM_PLAN}
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

  return (
    <div className="grid gap-4">
      <p role="status" className="font-semibold">
        {summaryLine({
          assigned: result.assigned.length,
          technicians: plans.length,
          unassigned: result.unassigned.length,
          skipped: result.skipped.length,
        })}
      </p>
      {showMap ? (
        // The map comes first on a phone and sits beside the cards on a wide screen,
        // staying in view while the cards scroll.
        <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
          <div className="lg:sticky lg:top-4 lg:order-2">
            <div className="h-[320px] lg:h-[calc(100vh-8rem)] lg:max-h-[640px]">
              <PlanMap data={mapData} office={office} selectedId={selected} onSelect={(id) => select(id, true)} />
            </div>
            <PlanMapKey data={mapData} hasOffice={office !== null} />
          </div>
          <div className="lg:order-1">{lists}</div>
        </div>
      ) : (
        lists
      )}
    </div>
  );
}
