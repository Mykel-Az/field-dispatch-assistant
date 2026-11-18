import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../../auth/useAuth';
import { arriveJob, completeJob, fetchMyJobs, incompleteJob } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { TechnicianJob } from '../../shared/api/models';
import { getOrgTimezone } from '../../shared/jobTime';
import { usePolling, notifyJobsChanged } from '../../shared/usePolling';
import { ui } from '../../shared/ui';
import ReasonDialog from '../components/ReasonDialog';
import TechJobCard, { type Action } from '../components/TechJobCard';
import { afterAction, currentJobId, progress } from '../jobsModel';

const todayLabel = () =>
  new Intl.DateTimeFormat('en-US', {
    timeZone: getOrgTimezone(),
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(new Date());

/** The technician's day: today's jobs in visiting order, with Arrive, Complete and Couldn’t finish. */
export default function TechnicianHome() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<TechnicianJob[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [notice, setNotice] = useState('');
  const [asking, setAsking] = useState<TechnicianJob | null>(null);
  const [dialogError, setDialogError] = useState('');
  const sending = useRef(false);

  const refresh = useCallback(async () => {
    if (sending.current) return; // do not swap the list under a tap that is in flight
    try {
      setJobs(await fetchMyJobs());
      setLoadError('');
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : 'Could not reach the server.');
    }
  }, []);
  // First load. Later refreshes (every 30 s, on focus, after a conflict) use `refresh`.
  useEffect(() => {
    let live = true;
    fetchMyJobs()
      .then((rows) => live && setJobs(rows))
      .catch(
        (err) =>
          live && setLoadError(err instanceof ApiError ? err.message : 'Could not reach the server.'),
      );
    return () => {
      live = false;
    };
  }, []);
  usePolling(refresh);

  async function run(job: TechnicianJob, action: Action, reason = '') {
    sending.current = true;
    setBusy(true);
    setMessage('');
    setNotice('');
    setDialogError('');
    try {
      const updated =
        action === 'arrive'
          ? await arriveJob(job.id)
          : action === 'complete'
            ? await completeJob(job.id)
            : await incompleteJob(job.id, reason);
      setJobs((current) => afterAction(current ?? [], updated));
      setAsking(null);
      if (action === 'incomplete') setNotice('Sent back to the dispatcher’s queue.');
      notifyJobsChanged();
    } catch (err) {
      const text = err instanceof ApiError ? err.message : 'Could not reach the server. Try again.';
      if (action === 'incomplete' && asking) setDialogError(text);
      else setMessage(text);
      // The job may have been changed or taken away by the office: show the truth.
      if (err instanceof ApiError && (err.status === 404 || err.status === 409)) {
        sending.current = false;
        await refresh();
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  function onAction(job: TechnicianJob, action: Action) {
    if (action === 'incomplete') {
      setDialogError('');
      setAsking(job); // the reason is asked first; nothing is sent yet
      return;
    }
    void run(job, action);
  }

  if (!user) return null;
  const list = jobs ?? [];
  const current = currentJobId(list);
  const ongoingId = list.find((j) => j.status === 'ongoing')?.id ?? null;
  const { done, total } = progress(list);

  return (
    <section className="mx-auto grid max-w-xl gap-4">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Hello, {user.full_name}</h1>
        <p className={ui.muted}>
          {todayLabel()}
          {total > 0 && ` · ${done} of ${total} done`}
        </p>
      </header>

      {loadError && <p role="alert" className={ui.notice}>{loadError}</p>}
      {message && <p role="alert" className={ui.notice}>{message}</p>}
      {notice && <p role="status" className="rounded-xl border border-line bg-brand-soft px-3 py-2 text-sm text-brand-ink">{notice}</p>}

      {jobs === null && !loadError && <p className={ui.centerNote}>Loading your jobs…</p>}
      {jobs !== null && list.length === 0 && (
        <div className={ui.card}>
          <p className="font-semibold">No jobs planned for today.</p>
          <p className={ui.muted}>New jobs show up here as soon as the dispatcher plans them.</p>
        </div>
      )}

      {list.map((job, i) => (
        <TechJobCard
          key={job.id}
          job={job}
          stop={i + 1}
          current={job.id === current}
          blocked={ongoingId !== null && ongoingId !== job.id}
          busy={busy}
          onAction={onAction}
        />
      ))}

      {asking && (
        <ReasonDialog
          jobTitle={asking.title}
          busy={busy}
          error={dialogError}
          onSend={(reason) => void run(asking, 'incomplete', reason)}
          onClose={() => setAsking(null)}
        />
      )}
    </section>
  );
}
