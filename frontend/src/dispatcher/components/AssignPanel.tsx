import { useEffect, useState } from 'react';
import {
  assignJob,
  fetchTechnicians,
  unassignJob,
} from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { JobDetail, Technician } from '../../shared/api/models';
import { notifyJobsChanged } from '../../shared/usePolling';
import { ui } from '../../shared/ui';

interface Props {
  job: JobDetail;
  /** Called with the fresh job after a change, or with null to reload (stale version). */
  onChanged: (job: JobDetail | null) => void;
}

/**
 * Hand-assign a job. The planner will do this automatically later; this is the
 * dispatcher's manual override, so it stays available afterwards.
 */
export default function AssignPanel({ job, onChanged }: Props) {
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [picked, setPicked] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const unassigned = job.status === 'unassigned';

  useEffect(() => {
    if (!unassigned) return;
    fetchTechnicians()
      .then((all) => setTechnicians(all.filter((t) => t.user.is_active)))
      .catch(() => setError('Could not load the technicians.'))
      .finally(() => setLoaded(true));
  }, [unassigned]);

  const wanted = new Set(job.acceptable_skills.map((s) => s.id));
  const matches = (t: Technician) => t.skills.some((s) => wanted.has(s.id));
  const sorted = [...technicians].sort(
    (a, b) =>
      Number(matches(b)) - Number(matches(a)) ||
      a.user.full_name.localeCompare(b.user.full_name),
  );
  const pickedTech = technicians.find((t) => t.id === picked);

  async function run(action: () => Promise<JobDetail>) {
    setBusy(true);
    setError('');
    try {
      const next = await action();
      notifyJobsChanged();
      onChanged(next);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Changed under us, or cannot take this action: say why, then refresh the job.
        setError(err.message);
        onChanged(null);
      } else {
        setError(
          err instanceof ApiError ? err.message : 'Could not reach the server.',
        );
      }
    } finally {
      setBusy(false);
    }
  }

  if (job.status === 'assigned') {
    return (
      <section className={ui.card}>
        <h2 className="mb-1 text-lg font-bold">
          Assigned to {job.technician?.full_name}
        </h2>
        <p className={ui.muted}>
          Not the right person? Send it back to the queue and pick again.
        </p>
        {error && (
          <p role="alert" className={`${ui.error} mt-2`}>
            {error}
          </p>
        )}
        <button
          className={`${ui.btnSmall} mt-3`}
          disabled={busy}
          onClick={() => run(() => unassignJob(job.id, job.version))}
        >
          {busy ? 'Working…' : 'Unassign'}
        </button>
      </section>
    );
  }
  if (!unassigned) return null;

  const noLocation =
    job.geocode_status === 'failed' || job.geocode_status === 'pending';
  return (
    <section className={ui.card}>
      <h2 className="mb-1 text-lg font-bold">Assign to…</h2>
      {noLocation ? (
        <p className={ui.notice}>
          This job has no map location yet, so it cannot be assigned.
        </p>
      ) : !loaded ? (
        <p className={ui.muted}>Loading technicians…</p>
      ) : technicians.length === 0 ? (
        <p className={ui.muted}>
          There are no active technicians. Add one under Technicians.
        </p>
      ) : (
        <>
          <p className={ui.muted}>
            Technicians with the right skill are listed first.
          </p>
          <ul
            className="mt-3 grid gap-2"
            role="radiogroup"
            aria-label="Technician"
          >
            {sorted.map((t) => {
              const ok = matches(t);
              const on = picked === t.id;
              return (
                <li key={t.id}>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={on}
                    onClick={() => setPicked(t.id)}
                    className={`flex min-h-11 w-full flex-wrap items-center justify-between gap-2 rounded-xl border-[1.5px] px-4 py-2 text-left ${
                      on
                        ? 'border-brand bg-brand-soft'
                        : 'border-line-strong bg-surface hover:bg-canvas'
                    }`}
                  >
                    <span>
                      <span className="font-semibold">{t.user.full_name}</span>
                      <span className="block text-xs text-ink-muted">
                        {t.skills.map((s) => s.name).join(', ') || 'No skills'}
                      </span>
                    </span>
                    <span
                      className={
                        ok
                          ? ui.chip
                          : 'rounded-full bg-warn-soft px-3 py-1 text-sm font-medium text-warn-ink'
                      }
                    >
                      {ok ? 'Right skill' : 'Different skill'}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {pickedTech && !matches(pickedTech) && (
            <p className={`${ui.muted} mt-2`}>
              {pickedTech.user.full_name} does not have the skill listed for
              this job. You can still assign them.
            </p>
          )}
          {error && (
            <p role="alert" className={`${ui.error} mt-2`}>
              {error}
            </p>
          )}
          <button
            className={`${ui.btn} mt-3`}
            disabled={busy || picked === null}
            onClick={() =>
              picked !== null &&
              run(() => assignJob(job.id, picked, job.version))
            }
          >
            {busy
              ? 'Assigning…'
              : pickedTech
                ? `Assign to ${pickedTech.user.full_name}`
                : 'Choose a technician'}
          </button>
        </>
      )}
    </section>
  );
}
