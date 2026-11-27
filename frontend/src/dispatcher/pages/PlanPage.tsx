import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../auth/useAuth';
import {
  fetchJobs,
  fetchMapJobs,
  fetchSchedule,
  fetchTechnicians,
  generateSchedule,
} from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { JobRow, ScheduleResult, Technician } from '../../shared/api/models';
import { NO_FILTERS } from '../../shared/filters';
import { useOffice } from '../../shared/map/useOffice';
import { ui } from '../../shared/ui';
import MetricsPanel from '../plan/MetricsPanel';
import PlanResults from '../plan/PlanResults';
import { addDays, MAX_DAYS_AHEAD, todayOnClock } from '../plan/planModel';

type Failure = {
  kind: 'config' | 'forbidden' | 'date' | 'other';
  message: string;
  /** What "Try again" repeats. */
  retry: 'load' | 'run';
};
type Place = { lat: number; lng: number };
type Outcome = {
  result: ScheduleResult;
  technicians: Technician[];
  jobs: Map<number, JobRow>;
  locations: Map<number, Place>;
};

function describe(error: unknown, retry: Failure['retry']): Failure {
  const action = retry === 'run' ? 'plan the day' : 'load the plan';
  if (error instanceof ApiError) {
    if (error.status === 409) return { kind: 'config', message: error.message, retry };
    if (error.status === 403) {
      return { kind: 'forbidden', message: 'Only dispatchers can use the planner.', retry };
    }
    if (error.status === 400) {
      return { kind: 'date', message: error.fieldErrors.date ?? error.message, retry };
    }
  }
  return {
    kind: 'other',
    message: `Could not ${action}. Check your connection and try again.`,
    retry,
  };
}

/** Job titles for the planned day, so rows can say more than "Job #12". Never fails the page. */
async function loadJobs(date: string): Promise<Map<number, JobRow>> {
  const byId = new Map<number, JobRow>();
  try {
    for (let page = 1; page <= 5; page += 1) {
      const response = await fetchJobs({ ...NO_FILTERS, date }, page);
      response.results.forEach((job) => byId.set(job.id, job));
      if (!response.next) break;
    }
  } catch {
    /* titles are a nicety: fall back to "Job #id" */
  }
  return byId;
}

/** Where the day's planned and unassigned jobs are, for the map. Never fails the page. */
async function loadLocations(date: string): Promise<Map<number, Place>> {
  try {
    const pins = await fetchMapJobs({
      ...NO_FILTERS,
      date,
      statuses: ['assigned', 'ongoing', 'unassigned'],
    });
    return new Map(pins.results.map((p) => [p.id, { lat: p.lat, lng: p.lng }]));
  } catch {
    return new Map(); // no map, but the plan itself is still there
  }
}

/** The names and titles a plan needs. Lookups that fail only cost the nicer labels. */
async function withContext(result: ScheduleResult): Promise<Outcome> {
  const [technicians, jobs, locations] = await Promise.all([
    fetchTechnicians().catch(() => [] as Technician[]),
    loadJobs(result.plan_date),
    loadLocations(result.plan_date),
  ]);
  return { result, technicians, jobs, locations };
}

const isEmpty = (r: ScheduleResult) =>
  r.assigned.length === 0 && r.unassigned.length === 0 && r.skipped.length === 0;

const dayLabel = (date: string) =>
  new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${date}T12:00:00Z`));

export default function PlanPage() {
  const { user } = useAuth();
  const timezone = user?.organization.timezone;
  const office = useOffice();
  const today = todayOnClock(timezone);
  // The chosen day lives in the URL, so coming back from a job opens the same day.
  const [params, setParams] = useSearchParams();
  const asked = params.get('date') ?? '';
  const date = /^\d{4}-\d{2}-\d{2}$/.test(asked) ? asked : today;
  const setDate = (next: string) => setParams(next ? { date: next } : {}, { replace: true });
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [reloads, setReloads] = useState(0);

  // Show what is already planned for the chosen day, so a reload keeps the plan.
  useEffect(() => {
    let current = true;
    void (async () => {
      setLoading(true);
      setFailure(null);
      setOutcome(null);
      try {
        const stored = await fetchSchedule(date);
        const next = isEmpty(stored) ? null : await withContext(stored);
        if (current) setOutcome(next);
      } catch (error) {
        if (current) setFailure(describe(error, 'load'));
      } finally {
        if (current) setLoading(false);
      }
    })();
    return () => {
      current = false;
    };
  }, [date, reloads]);

  // One button: the first run plans the queue; once the planner has placed jobs for the day
  // the same button redoes its own choices (ADR-026), which also picks up new jobs.
  const hasPlanned = outcome?.result.assigned.some((a) => a.placed_by === 'planner') ?? false;

  async function run(replan = false) {
    setRunning(true);
    setFailure(null);
    try {
      const ran = await generateSchedule(date, replan);
      // A run answers for the jobs it just looked at. Show the whole day instead, so
      // running twice does not make the first run's jobs vanish from the page.
      const whole = await fetchSchedule(date).catch(() => ran);
      setOutcome(await withContext(whole));
    } catch (error) {
      setFailure(describe(error, 'run'));
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className={ui.card}>
      <h1 className="mb-1 text-2xl font-semibold">Plan the day</h1>
      <p className={`${ui.muted} mb-4`}>
        Assigns the day’s unassigned jobs to technicians and explains each choice. Jobs that are
        already assigned stay with their technician, and new jobs are planned around them.
        Once the day has been planned, the button becomes Plan again: it redoes the planner’s own
        choices (after a setting changed, say) and leaves hand-assigned and started jobs alone.
      </p>

      <form
        className="mb-6 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void run(hasPlanned);
        }}
      >
        <label className={ui.label}>
          Day
          <input
            type="date"
            className={ui.input}
            value={date}
            min={today}
            max={addDays(today, MAX_DAYS_AHEAD)}
            required
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
        <button
          type="submit"
          className={ui.btn}
          disabled={running || loading || !date}
          title={
            hasPlanned
              ? 'Return the jobs the planner placed (not ones you assigned by hand, or started) to the queue and plan them again, with any new jobs'
              : 'Assign this day’s unassigned jobs'
          }
        >
          {running ? 'Planning…' : hasPlanned ? 'Plan again' : 'Run plan'}
        </button>
      </form>

      {failure && (
        <div role="alert" className="mb-4">
          <p className={ui.error}>{failure.message}</p>
          {failure.kind === 'config' && (
            <Link className="text-sm font-semibold text-brand-ink underline" to="/organization">
              Open organization settings
            </Link>
          )}
          {failure.kind === 'other' && (
            <button
              className={`${ui.btnSmall} mt-2`}
              onClick={() => (failure.retry === 'run' ? void run() : setReloads((n) => n + 1))}
              disabled={running || loading}
            >
              Try again
            </button>
          )}
        </div>
      )}

      {loading && !outcome && <p className={ui.muted}>Loading the plan…</p>}

      {!loading && !outcome && !failure && (
        <p className={ui.muted}>
          Nothing planned for {dayLabel(date)} yet. Run plan to assign its unassigned jobs.
        </p>
      )}

      {outcome && (
        <>
          <h2 className="mb-3 text-xl font-bold">{dayLabel(outcome.result.plan_date)}</h2>
          <MetricsPanel date={outcome.result.plan_date} refreshKey={outcome} />
          <PlanResults
            result={outcome.result}
            technicians={outcome.technicians}
            jobs={outcome.jobs}
            timezone={timezone}
            locations={outcome.locations}
            office={office}
          />
        </>
      )}
    </section>
  );
}
