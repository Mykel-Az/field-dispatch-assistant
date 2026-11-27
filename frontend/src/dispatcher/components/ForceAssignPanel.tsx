import { useEffect, useState } from 'react';
import { fetchJob, forceAssignJob, type ForceAssignResult } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { JobDetail } from '../../shared/api/models';
import { splitLocal } from '../../shared/jobTime';
import { ui } from '../../shared/ui';
import { notifyJobsChanged } from '../../shared/usePolling';

interface Props {
  job: JobDetail;
  technicianId: number;
  technicianName: string;
  /** Called with the fresh job after a change, or with null to reload (stale version). */
  onChanged: (job: JobDetail | null) => void;
}

interface Bumped {
  id: number;
  title: string;
}

/**
 * Mount it with `key={technician id}` so a different technician starts from a clean state.
 *
 * Give an urgent job to a chosen technician now. If they cannot reach it in time, the
 * jobs they have not started that stand in the way go back to the queue. The preview
 * (a dry run on the server) shows exactly which, before anything changes.
 */
export default function ForceAssignPanel({ job, technicianId, technicianName, onChanged }: Props) {
  const [preview, setPreview] = useState<ForceAssignResult | null>(null);
  const [bumped, setBumped] = useState<Bumped[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const result = await forceAssignJob(job.id, technicianId, job.version, true);
        if (!live) return;
        // Titles only: the preview names the jobs, it does not show their customers.
        const titles = await Promise.all(
          result.bumped_job_ids.map((id) =>
            fetchJob(id)
              .then((j) => ({ id, title: j.title }))
              .catch(() => ({ id, title: `Job #${id}` })),
          ),
        );
        if (!live) return;
        setPreview(result);
        setBumped(titles);
      } catch (err) {
        if (live) setError(err instanceof ApiError ? err.message : 'Could not reach the server.');
      }
    })();
    return () => {
      live = false;
    };
  }, [job.id, job.version, technicianId]);

  async function confirm() {
    setBusy(true);
    setError('');
    try {
      const result = await forceAssignJob(job.id, technicianId, job.version);
      notifyJobsChanged();
      onChanged(result.job);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.');
      if (err instanceof ApiError && err.status === 409) onChanged(null);
    } finally {
      setBusy(false);
    }
  }

  const late = preview !== null && preview.slack_minutes < 0;
  return (
    <div className="mt-4 rounded-xl border border-line-strong bg-canvas p-4" aria-live="polite">
      <h3 className="font-bold">Urgent: send {technicianName} now</h3>
      {error && (
        <p role="alert" className={`${ui.error} mt-2`}>
          {error}
        </p>
      )}
      {!preview && !error && <p className={`${ui.muted} mt-1`}>Checking their day…</p>}
      {preview && (
        <>
          <p className="mt-1 text-sm">
            {technicianName} would arrive at{' '}
            <strong>{splitLocal(preview.estimated_arrival).time}</strong>
            {late
              ? `, ${Math.ceil(-preview.slack_minutes)} min after the deadline.`
              : `, with ${Math.floor(preview.slack_minutes)} min to spare.`}
          </p>
          {bumped.length > 0 ? (
            <div className="mt-2">
              <p className="text-sm font-medium">
                {bumped.length === 1 ? 'This job goes' : `These ${bumped.length} jobs go`} back to the queue:
              </p>
              <ul className="mt-1 list-disc pl-5 text-sm">
                {bumped.map((b) => (
                  <li key={b.id}>{b.title}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className={`${ui.muted} mt-1`}>No other job is affected.</p>
          )}
          {late && (
            <p role="status" className={`${ui.notice} mt-2`}>
              {bumped.length === 0
                ? 'Nothing this technician has can be moved, so the job will be late.'
                : 'Even after these changes the job will be late.'}{' '}
              Another technician may be a better choice.
            </p>
          )}
          <button className={`${ui.btnDanger} mt-3`} disabled={busy} onClick={confirm}>
            {busy ? 'Assigning…' : bumped.length > 0 ? `Force assign and return ${bumped.length} to the queue` : 'Force assign'}
          </button>
        </>
      )}
    </div>
  );
}
