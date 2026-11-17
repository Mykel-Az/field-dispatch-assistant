import { useCallback, useState } from 'react';
import { retryGeocode } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { JobDetail } from '../../shared/api/models';
import PinMap, { type LatLng } from '../../shared/map/PinMap';
import { useOffice } from '../../shared/map/useOffice';
import { notifyJobsChanged } from '../../shared/usePolling';
import { ui } from '../../shared/ui';
import LocationDialog from './LocationDialog';

const SAYS: Record<string, string> = {
  ok: 'Found from the address.',
  approximate: 'Only the area was found, not the exact spot.',
  manual: 'Placed on the map by hand. Approximate: it may not be the exact address.',
  failed: 'We could not find this address.',
  pending: 'No location yet.',
};

interface Props {
  job: JobDetail;
  /** Fresh job after a change, or null to reload (someone else changed it first). */
  onChanged: (job: JobDetail | null) => void;
}

/** Where the job is, and how to fix it: try the address again, or place the pin on a larger map. */
export default function LocationPanel({ job, onChanged }: Props) {
  const saved: LatLng | null = job.lat != null && job.lng != null ? { lat: job.lat, lng: job.lng } : null;
  const office = useOffice();
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const close = useCallback(() => setEditing(false), []);

  if (job.status !== 'unassigned') return null; // a planned job's location is frozen

  const needsHelp = job.geocode_status !== 'ok' && job.geocode_status !== 'manual';

  async function retry() {
    setBusy(true);
    setError('');
    try {
      const next = await retryGeocode(job.id, job.version);
      notifyJobsChanged();
      onChanged(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.');
      if (err instanceof ApiError && err.status === 409) onChanged(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={ui.card}>
      <h2 className="mb-1 text-lg font-bold">Location</h2>
      <p className={needsHelp ? 'text-sm font-medium text-warn-ink' : ui.muted}>
        {SAYS[job.geocode_status] ?? ''}
        {needsHelp && ' Place the pin on the map, or check the address and try again.'}
      </p>
      <div className="mt-3">
        <PinMap pin={saved} office={office} height={220} />
      </div>
      {error && <p role="alert" className={`${ui.error} mt-2`}>{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={needsHelp ? ui.btn : ui.btnSmall} onClick={() => setEditing(true)}>
          Edit location
        </button>
        {needsHelp && (
          <button type="button" className={ui.btnSmall} disabled={busy} onClick={() => void retry()}>
            {busy ? 'Looking…' : 'Try the address again'}
          </button>
        )}
      </div>
      {editing && <LocationDialog job={job} office={office} onChanged={onChanged} onClose={close} />}
    </section>
  );
}
