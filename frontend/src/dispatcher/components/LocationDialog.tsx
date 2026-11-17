import { useEffect, useRef, useState } from 'react';
import { pinJob } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { JobDetail } from '../../shared/api/models';
import PinMap, { type LatLng } from '../../shared/map/PinMap';
import { notifyJobsChanged } from '../../shared/usePolling';
import { ui } from '../../shared/ui';

interface Props {
  job: JobDetail;
  office: LatLng | null;
  /** Fresh job after a save, or null to reload (someone else changed it first). */
  onChanged: (job: JobDetail | null) => void;
  onClose: () => void;
}

/**
 * A large map for placing the pin: the small one on the page is for looking, this
 * one is for working. Nothing is saved until "Save location"; Cancel and Escape
 * leave the job as it was.
 */
export default function LocationDialog({ job, office, onChanged, onClose }: Props) {
  const saved: LatLng | null = job.lat != null && job.lng != null ? { lat: job.lat, lng: job.lng } : null;
  const [draft, setDraft] = useState<LatLng | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const panel = useRef<HTMLDivElement>(null);

  // Escape closes; the page behind does not scroll; focus returns to the button that opened this.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panel.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      opener?.focus?.();
    };
  }, [onClose]);

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError('');
    try {
      const next = await pinJob(job.id, draft.lat, draft.lng, job.version);
      notifyJobsChanged();
      onChanged(next);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.');
      if (err instanceof ApiError && err.status === 409) onChanged(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-stretch justify-center bg-ink/60 sm:items-center sm:p-6">
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="location-dialog-title"
        tabIndex={-1}
        className="flex h-full w-full max-w-5xl flex-col gap-3 bg-surface p-4 shadow-xl outline-none sm:h-[90vh] sm:rounded-card"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 id="location-dialog-title" className="text-lg font-bold">Edit location</h2>
            <p className={ui.muted}>
              Customer’s address: {job.address}. Click the map, or drag the pin, to where the job is.
            </p>
          </div>
          <button type="button" className={ui.btnSmall} onClick={onClose}>Cancel</button>
        </div>

        <div className="min-h-0 flex-1">
          <PinMap pin={draft ?? saved} onPick={setDraft} office={office} wheelZoom height="100%" />
        </div>

        <p className={ui.muted}>
          {draft
            ? 'Pin moved. It is saved as an approximate position and may not be the exact address; the address above stays as the customer gave it.'
            : 'Nothing changed yet.'}
        </p>
        {error && <p role="alert" className={ui.error}>{error}</p>}
        <div className="flex flex-wrap gap-2">
          <button type="button" className={ui.btn} disabled={busy || !draft} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save location'}
          </button>
          {draft && (
            <button type="button" className={ui.btnSmall} disabled={busy} onClick={() => setDraft(null)}>
              Undo move
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
