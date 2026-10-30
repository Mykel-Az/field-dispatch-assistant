import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { cancelJob, fetchJob } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import { CATEGORY_LABEL, type JobDetail } from '../../shared/api/models';
import StatusBadge from '../../shared/components/StatusBadge';
import { formatSlot, formatStamp, placeLine } from '../../shared/jobTime';
import { CANCELABLE, isJobStatus, STATUS_META } from '../../shared/status';
import { useOrgTimezone } from '../../shared/useOrgTimezone';
import { notifyJobsChanged } from '../../shared/usePolling';
import { ui } from '../../shared/ui';
import AssignPanel from '../components/AssignPanel';
import JobForm from '../components/JobForm';
import LocationPanel from '../components/LocationPanel';

const FINISHED = new Set(['completed', 'failed', 'canceled']);

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-sm font-medium text-ink-muted">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

function History({ job }: { job: JobDetail }) {
  useOrgTimezone();
  return (
    <section className={ui.card} aria-labelledby="history-heading">
      <h2 id="history-heading" className="mb-3 text-lg font-bold">History</h2>
      <ol className="grid gap-4">
        {[...job.history].reverse().map((h) => {
          const to = isJobStatus(h.to_status) ? STATUS_META[h.to_status].label : h.to_status;
          const from = h.from_status && isJobStatus(h.from_status) ? STATUS_META[h.from_status].label : '';
          return (
            <li key={h.id} className="border-l-2 border-line pl-4">
              <div className="font-semibold">{from ? `${from} → ${to}` : `Created as ${to}`}</div>
              {h.reason && <div className="text-sm">“{h.reason}”</div>}
              <div className="text-sm text-ink-muted">
                {h.changed_by?.full_name ?? 'System'} · {formatStamp(h.created_at)}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function CancelPanel({ job, onCanceled }: { job: JobDetail; onCanceled: (j: JobDetail) => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!reason.trim()) {
      setError('Say why the job is being canceled.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const canceled = await cancelJob(job.id, reason.trim());
      notifyJobsChanged();
      onCanceled(canceled);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not cancel the job.');
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className={`${ui.btnDanger} justify-self-start`} onClick={() => setOpen(true)}>
        Cancel job
      </button>
    );
  }
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl border border-danger/40 p-4">
      <label className={ui.label}>
        Why is this job being canceled?
        <textarea className={ui.input} rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
      </label>
      {job.technician && (
        <p className={ui.muted}>{job.technician.full_name} will be released from this job.</p>
      )}
      {error && <p role="alert" className={ui.error}>{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button className={ui.btnDanger} disabled={busy}>{busy ? 'Canceling…' : 'Confirm cancel'}</button>
        <button type="button" className={ui.btnSmall} onClick={() => setOpen(false)}>Keep job</button>
      </div>
    </form>
  );
}

export default function JobPage() {
  useOrgTimezone();
  const { id } = useParams();
  const jobId = Number(id);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    try {
      setJob(await fetchJob(jobId));
      setError('');
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 404
          ? 'This job does not exist.'
          : err instanceof ApiError
            ? err.message
            : 'Could not load the job.',
      );
    }
  }, [jobId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetch on mount
    void load();
  }, [load]);

  if (error) {
    return (
      <section>
        <p role="alert" className={ui.error}>{error}</p>
        <Link to="/jobs" className="text-brand hover:underline">Back to jobs</Link>
      </section>
    );
  }
  if (!job) return <p className={ui.muted}>Loading…</p>;

  const needsLocation = job.geocode_status === 'failed' || job.geocode_status === 'pending';
  const finished = FINISHED.has(job.status);

  return (
    <section>
      <Link to="/jobs" className="text-sm text-brand hover:underline">← All jobs</Link>
      <div className="mt-2 mb-5 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight">{job.title}</h1>
        {job.is_urgent && (
          <span className="rounded-full bg-danger-soft px-3 py-0.5 text-sm font-bold text-danger">Urgent</span>
        )}
        <StatusBadge status={job.status} />
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid gap-5">
          <section className={ui.card}>
            {editing ? (
              <JobForm
                // reset the form's state whenever a newer version of the job arrives
                key={job.version}
                job={job}
                onCancel={() => setEditing(false)}
                onReload={() => {
                  setEditing(false);
                  void load();
                }}
                onSaved={(saved) => {
                  setJob(saved);
                  setEditing(false);
                }}
              />
            ) : (
              <>
                <dl className="grid gap-4 sm:grid-cols-2">
                  <Fact label="Customer">
                    {job.customer_name}
                    {job.customer_phone && <div className="text-sm text-ink-muted">{job.customer_phone}</div>}
                  </Fact>
                  <Fact label="Category">{CATEGORY_LABEL[job.category]}</Fact>
                  <Fact label="Address">
                    {job.address}
                    <div className="text-sm text-ink-muted">{placeLine(job)}</div>
                    {needsLocation && (
                      <div className="mt-1 text-sm text-warn-ink">
                        Location needs attention: we could not place this address on the map.
                      </div>
                    )}
                  </Fact>
                  <Fact label="Time window">
                    {formatSlot(job.slot_start, job.slot_end)}
                    <div className="text-sm text-ink-muted">About {job.estimated_duration_minutes} min</div>
                  </Fact>
                  <Fact label="Technician">{job.technician?.full_name ?? 'Not assigned'}</Fact>
                  <Fact label="Skills that can do it">
                    <div className="flex flex-wrap gap-1.5">
                      {job.acceptable_skills.map((s) => (
                        <span key={s.id} className={ui.chip}>{s.name}</span>
                      ))}
                    </div>
                  </Fact>
                </dl>
                {job.description && (
                  <div className="mt-4">
                    <div className="text-sm font-medium text-ink-muted">Problem, as the customer describes it</div>
                    <p className="mt-0.5 whitespace-pre-line">{job.description}</p>
                  </div>
                )}
                {!finished && (
                  <div className="mt-6 flex flex-wrap gap-2">
                    <button className={ui.btn} onClick={() => setEditing(true)}>Edit job</button>
                  </div>
                )}
              </>
            )}
          </section>

          {!editing && (
            <AssignPanel job={job} onChanged={(next) => (next ? setJob(next) : void load())} />
          )}

          {!editing && (
            <LocationPanel job={job} onChanged={(next) => (next ? setJob(next) : void load())} />
          )}

          {!editing && isJobStatus(job.status) && CANCELABLE.has(job.status) && (
            <CancelPanel job={job} onCanceled={setJob} />
          )}
        </div>

        <History job={job} />
      </div>
    </section>
  );
}
