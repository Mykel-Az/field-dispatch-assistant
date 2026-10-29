import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchJobs, fetchTechnicians } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import { CATEGORY_LABEL, type JobRow, type Page, type Technician } from '../../shared/api/models';
import StatusBadge from '../../shared/components/StatusBadge';
import StatusPin from '../../shared/components/StatusPin';
import { formatSlot, placeLine } from '../../shared/jobTime';
import { isJobStatus, JOB_STATUSES, STATUS_META } from '../../shared/status';
import { ui } from '../../shared/ui';

const PAGE_SIZE = 50;

function LocationFlag() {
  return (
    <span className={ui.flag}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 3 2 21h20L12 3Z" />
        <path d="M12 10v5M12 18v.01" />
      </svg>
      Location needs attention
    </span>
  );
}

function JobCard({ job }: { job: JobRow }) {
  const meta = isJobStatus(job.status) ? STATUS_META[job.status] : null;
  const needsLocation = job.geocode_status === 'failed' || job.geocode_status === 'pending';
  return (
    <li>
      <Link
        to={`/jobs/${job.id}`}
        className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-card bg-surface p-4 pl-5 shadow-sm ring-1 ring-line hover:ring-line-strong focus-visible:outline-2 focus-visible:outline-brand lg:grid lg:grid-cols-[0.375rem_minmax(0,2fr)_minmax(0,2fr)_11rem_8.5rem]"
      >
        <span aria-hidden="true" className={`w-1.5 self-stretch rounded-full ${meta?.bar ?? 'bg-line'}`} />
        <div className="min-w-0 flex-[1_1_16rem]">
          <div className="flex flex-wrap items-center gap-2 text-lg font-bold">
            {job.title}
            {job.is_urgent && (
              <span className="rounded-full bg-danger-soft px-2.5 py-0.5 text-xs font-bold text-danger">Urgent</span>
            )}
          </div>
          <div className="text-ink-muted">
            {job.customer_name} · {CATEGORY_LABEL[job.category]}
          </div>
        </div>
        <div className="min-w-0 flex-[1_1_14rem]">
          <div>{job.address}</div>
          {needsLocation ? (
            <LocationFlag />
          ) : (
            <div className="text-sm text-ink-muted">{placeLine(job)}</div>
          )}
        </div>
        <div className="flex-[0_1_11rem]">
          <div className="font-semibold">{formatSlot(job.slot_start, job.slot_end)}</div>
          <div className="text-sm text-ink-muted">{job.technician?.full_name ?? 'Not assigned'}</div>
        </div>
        <span className="lg:justify-self-end"><StatusBadge status={job.status} /></span>
      </Link>
    </li>
  );
}

export default function JobsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? '';
  const scheduledDate = params.get('scheduled_date') ?? '';
  const technician = params.get('technician') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);

  const [data, setData] = useState<Page<JobRow> | null>(null);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setData(await fetchJobs({ status, scheduled_date: scheduledDate, technician, page }));
      setError('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load jobs.');
    }
  }, [status, scheduledDate, technician, page]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetch when filters change
    void load();
  }, [load]);

  useEffect(() => {
    fetchTechnicians().then(setTechnicians).catch(() => setTechnicians([]));
  }, []);

  function setFilter(name: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    next.delete('page'); // a new filter starts at page 1
    setParams(next, { replace: true });
  }

  function goToPage(n: number) {
    const next = new URLSearchParams(params);
    if (n > 1) next.set('page', String(n));
    else next.delete('page');
    setParams(next);
  }

  const filtered = Boolean(status || scheduledDate || technician);
  const lastPage = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1;

  return (
    <section>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Jobs</h1>
          <p className="text-ink-muted">
            {data ? `${data.count} ${data.count === 1 ? 'job' : 'jobs'}${filtered ? ' match your filters' : ''}` : ' '}
          </p>
        </div>
        <Link to="/jobs/new" className={`${ui.btn} inline-flex items-center`}>+ New job</Link>
      </div>

      <div className="my-5 flex flex-wrap gap-3">
        <label className={ui.label}>
          Status
          <select className={`${ui.input} min-w-40`} value={status} onChange={(e) => setFilter('status', e.target.value)}>
            <option value="">All statuses</option>
            {JOB_STATUSES.map((s) => (
              <option key={s} value={s}>{STATUS_META[s].label}</option>
            ))}
          </select>
        </label>
        <label className={ui.label}>
          Date
          <input className={ui.input} type="date" value={scheduledDate} onChange={(e) => setFilter('scheduled_date', e.target.value)} />
        </label>
        <label className={ui.label}>
          Technician
          <select className={`${ui.input} min-w-44`} value={technician} onChange={(e) => setFilter('technician', e.target.value)}>
            <option value="">Everyone</option>
            {technicians.map((t) => (
              <option key={t.id} value={t.id}>{t.user.full_name}</option>
            ))}
          </select>
        </label>
        {filtered && (
          <button className={`${ui.btnSmall} self-end`} onClick={() => setParams({}, { replace: true })}>
            Clear filters
          </button>
        )}
      </div>

      {error && <p role="alert" className={ui.error}>{error}</p>}
      {data === null && !error && <p className={ui.muted}>Loading…</p>}
      {data?.results.length === 0 && (
        <p className={ui.centerNote}>
          {filtered ? 'No jobs match these filters.' : 'No jobs yet. Create the first one.'}
        </p>
      )}

      {data && data.results.length > 0 && (
        <ul className="grid gap-3">
          {data.results.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </ul>
      )}

      {data && lastPage > 1 && (
        <div className="mt-5 flex items-center justify-center gap-4">
          <button className={ui.btnSmall} disabled={!data.previous} onClick={() => goToPage(page - 1)}>Previous</button>
          <span className={ui.muted}>Page {page} of {lastPage}</span>
          <button className={ui.btnSmall} disabled={!data.next} onClick={() => goToPage(page + 1)}>Next</button>
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-card bg-brand-soft px-5 py-4">
        <strong className="text-brand-ink">Map pins use these colours too</strong>
        {JOB_STATUSES.map((s) => (
          <span key={s} className="inline-flex items-center gap-1.5 text-sm">
            <StatusPin status={s} size={22} />
            {STATUS_META[s].label}
          </span>
        ))}
      </div>
    </section>
  );
}
