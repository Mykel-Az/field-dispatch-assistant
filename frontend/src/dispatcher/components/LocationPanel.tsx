import { useState } from 'react';
import { pinJob, retryGeocode } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { JobDetail } from '../../shared/api/models';
import PinMap, { type LatLng } from '../../shared/map/PinMap';
import { ui } from '../../shared/ui';

const SAYS: Record<string, string> = {
  ok: 'Found from the address.',
  approximate: 'Only the area was found, not the exact spot.',
  manual: 'Placed on the map by hand.',
  failed: 'We could not find this address.',
  pending: 'No location yet.',
};

interface Props {
  job: JobDetail;
  /** Fresh job after a change, or null to reload (someone else changed it first). */
  onChanged: (job: JobDetail | null) => void;
}

/** Where the job is, and how to fix it: try the address again, or click the map. */
export default function LocationPanel({ job, onChanged }: Props) {
  const saved: LatLng | null = job.lat != null && job.lng != null ? { lat: job.lat, lng: job.lng } : null;
  const [draft, setDraft] = useState<LatLng | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (job.status !== 'unassigned') return null; // a planned job's location is frozen

  const needsHelp = job.geocode_status !== 'ok' && job.geocode_status !== 'manual';

  async function run(action: () => Promise<JobDetail>) {
    setBusy(true);
    setError('');
    try {
      onChanged(await action());
      setDraft(null);
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
        <PinMap pin={draft ?? saved} onPick={setDraft} height={260} />
      </div>
      <p className={`${ui.muted} mt-2`}>Click the map, or drag the pin, to put it in the right place.</p>
      {error && <p role="alert" className={`${ui.error} mt-2`}>{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {draft && (
          <>
            <button className={ui.btn} disabled={busy} onClick={() => run(() => pinJob(job.id, draft.lat, draft.lng, job.version))}>
              {busy ? 'Saving…' : 'Save this location'}
            </button>
            <button className={ui.btnSmall} disabled={busy} onClick={() => setDraft(null)}>Undo</button>
          </>
        )}
        {!draft && needsHelp && (
          <button className={ui.btnSmall} disabled={busy} onClick={() => run(() => retryGeocode(job.id, job.version))}>
            {busy ? 'Looking…' : 'Try the address again'}
          </button>
        )}
      </div>
    </section>
  );
}
