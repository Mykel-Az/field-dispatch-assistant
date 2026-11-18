import { useEffect, useRef, useState } from 'react';
import { ui } from '../../shared/ui';

interface Props {
  jobTitle: string;
  busy: boolean;
  error: string;
  onSend: (reason: string) => void;
  onClose: () => void;
}

/**
 * Why the job could not be finished. The reason is required: the dispatcher reads it
 * on the job's history when deciding what to do next. Nothing is sent until the
 * button; both buttons are disabled while sending so a second tap cannot repeat it.
 */
export default function ReasonDialog({ jobTitle, busy, error, onSend, onClose }: Props) {
  const [reason, setReason] = useState('');
  const [missing, setMissing] = useState(false);
  const field = useRef<HTMLTextAreaElement>(null);
  const closing = useRef(onClose);
  useEffect(() => {
    closing.current = onClose;
  });

  // Escape closes (unless sending); the page behind does not scroll; focus returns.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    field.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
      opener?.focus?.();
    };
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && closing.current();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [busy]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!reason.trim()) {
      setMissing(true);
      return;
    }
    onSend(reason.trim());
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-end justify-center bg-ink/60 sm:items-center sm:p-6">
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="reason-title"
        onSubmit={submit}
        className="grid w-full max-w-md gap-3 rounded-t-card bg-surface p-5 shadow-xl sm:rounded-card"
      >
        <h2 id="reason-title" className="text-lg font-bold">Couldn’t finish this job?</h2>
        <p className={ui.muted}>
          “{jobTitle}” goes back to the dispatcher’s queue. Tell them what happened.
        </p>
        <label className={ui.label}>
          What went wrong
          <textarea
            ref={field}
            className={`${ui.input} min-h-28`}
            value={reason}
            maxLength={500}
            disabled={busy}
            aria-invalid={missing}
            onChange={(e) => {
              setReason(e.target.value);
              setMissing(false);
            }}
          />
        </label>
        {missing && <p role="alert" className={ui.error}>Say what went wrong.</p>}
        {error && <p role="alert" className={ui.error}>{error}</p>}
        <div className="grid gap-2">
          <button type="submit" className={`${ui.btnDanger} min-h-14 text-base`} disabled={busy}>
            {busy ? 'Sending…' : 'Send back to the queue'}
          </button>
          <button type="button" className={`${ui.btnSmall} min-h-14 text-base`} disabled={busy} onClick={onClose}>
            Keep working
          </button>
        </div>
      </form>
    </div>
  );
}
