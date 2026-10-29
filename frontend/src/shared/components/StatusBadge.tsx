import { isJobStatus, STATUS_META } from '../status';

/** Coloured pill with the status name. The text carries the meaning, colour only helps. */
export default function StatusBadge({ status }: { status: string }) {
  if (!isJobStatus(status)) {
    return <span className="text-sm text-ink-muted">{status}</span>;
  }
  const meta = STATUS_META[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold ${meta.badge}`}
    >
      <span aria-hidden="true" className="size-2 rounded-full bg-current" />
      {meta.label}
    </span>
  );
}
