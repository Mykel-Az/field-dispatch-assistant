import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchJob, fetchMapJobs, type MapPin } from '../../shared/api/client';
import type { JobDetail } from '../../shared/api/models';
import JobFilterBar from '../../shared/components/JobFilterBar';
import StatusBadge from '../../shared/components/StatusBadge';
import StatusPin from '../../shared/components/StatusPin';
import { NO_FILTERS, readFilters, writeFilters } from '../../shared/filters';
import { formatSlot, placeLine } from '../../shared/jobTime';
import JobsMap from '../../shared/map/JobsMap';
import { isJobStatus, JOB_STATUSES, STATUS_META } from '../../shared/status';
import { useOrgTimezone } from '../../shared/useOrgTimezone';
import { usePolling } from '../../shared/usePolling';
import { ui } from '../../shared/ui';

const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export default function MapPage() {
  useOrgTimezone();
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => readFilters(params), [params]);

  const [pins, setPins] = useState<MapPin[]>([]);
  const [truncated, setTruncated] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [failed, setFailed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [detailError, setDetailError] = useState(false);
  const latest = useRef(0);

  const refresh = useCallback(async () => {
    const mine = ++latest.current; // a slow older answer must not overwrite a newer one
    setRefreshing(true);
    try {
      const data = await fetchMapJobs(filters);
      if (mine !== latest.current) return;
      setPins(data.results);
      setTruncated(data.truncated);
      setUpdatedAt(new Date());
      setFailed(false);
    } catch {
      if (mine === latest.current) setFailed(true); // keep showing the last good pins
    } finally {
      if (mine === latest.current) {
        setLoaded(true);
        setRefreshing(false);
      }
    }
  }, [filters]);

  // Load now and whenever a filter changes; usePolling keeps it fresh after that
  // (every 30 s while visible, on tab focus, and after any job change by this user).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetch on mount
    void refresh();
  }, [refresh]);
  usePolling(() => void refresh());

  // Show the selected job's details under the map; reload them with every refresh.
  useEffect(() => {
    if (selectedId === null) return;
    let live = true;
    fetchJob(selectedId)
      .then((j) => live && (setDetail(j), setDetailError(false)))
      .catch(() => live && setDetailError(true));
    return () => {
      live = false;
    };
  }, [selectedId, updatedAt]);

  function changeFilters(next: typeof filters) {
    setParams(writeFilters(params, next), { replace: true });
    setSelectedId(null);
    setDetail(null);
  }

  const counts = JOB_STATUSES.map((s) => [s, pins.filter((p) => p.status === s).length] as const);
  const shown = detail && detail.id === selectedId ? detail : null;

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-3xl font-bold tracking-tight">Map</h1>
      </div>

      <JobFilterBar value={filters} onChange={changeFilters} onClear={() => changeFilters(NO_FILTERS)} />

      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2" aria-live="polite">
        <span className={ui.muted}>
          {failed
            ? 'Could not refresh. Showing the last update'
            : updatedAt
              ? `Last updated ${clock.format(updatedAt)}`
              : 'Loading…'}
          {failed && updatedAt ? ` from ${clock.format(updatedAt)}.` : ''}
        </span>
        <button className={ui.btnSmall} onClick={() => void refresh()} disabled={refreshing}>
          {refreshing ? 'Refreshing…' : failed ? 'Try again' : 'Refresh'}
        </button>
        {failed && <span role="alert" className={ui.error}>The server did not answer.</span>}
      </div>

      {truncated && (
        <p className={`${ui.notice} mb-3`}>Too many jobs to show at once. Narrow it down with the filters.</p>
      )}

      {loaded && pins.length === 0 && !failed ? (
        <div className={`${ui.card} text-center text-ink-muted`}>
          No located jobs{params.toString() ? ' for these filters' : ''}.{' '}
          <Link to="/jobs/new" className="text-brand hover:underline">Create a job</Link>
        </div>
      ) : (
        <JobsMap pins={pins} selectedId={selectedId} onSelect={setSelectedId} />
      )}

      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-muted" aria-label="Pin colours">
        {counts.map(([s, n]) => (
          <li key={s} className="flex items-center gap-1.5">
            <StatusPin status={s} size={18} /> {STATUS_META[s].label} ({n})
          </li>
        ))}
      </ul>

      {selectedId !== null && (
        <div className={`${ui.card} mt-4`}>
          {detailError && !shown ? (
            <p className={ui.error}>Could not load this job.</p>
          ) : !shown ? (
            <p className={ui.muted}>Loading…</p>
          ) : (
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-bold">{shown.title}</h2>
                  {shown.is_urgent && (
                    <span className="rounded-full bg-danger-soft px-3 py-0.5 text-sm font-bold text-danger">Urgent</span>
                  )}
                  {isJobStatus(shown.status) && <StatusBadge status={shown.status} />}
                </div>
                <p className="mt-1">{shown.customer_name} · {shown.address}</p>
                <p className={ui.muted}>
                  {placeLine(shown)} · {formatSlot(shown.slot_start, shown.slot_end)} ·{' '}
                  {shown.technician?.full_name ?? 'Not assigned'}
                </p>
              </div>
              <Link to={`/jobs/${shown.id}`} className={ui.btn + ' inline-flex items-center'}>Open job</Link>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
