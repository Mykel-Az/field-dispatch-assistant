import { useEffect, useState } from 'react';
import { fetchTechnicians } from '../api/client';
import type { Technician } from '../api/models';
import { hasFilters, toggleStatus, toggleTechnician, type JobFilterValues } from '../filters';
import { JOB_STATUSES, STATUS_META } from '../status';
import { ui } from '../ui';
import StatusPin from './StatusPin';

interface Props {
  value: JobFilterValues;
  onChange: (next: JobFilterValues) => void;
  onClear: () => void;
}

/** Status chips (pick any number), a day and a technician. All of them combine. */
export default function JobFilterBar({ value, onChange, onClear }: Props) {
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  useEffect(() => {
    fetchTechnicians().then(setTechnicians).catch(() => setTechnicians([]));
  }, []);

  const names = technicians
    .filter((t) => value.technicians.includes(String(t.id)))
    .map((t) => t.user.full_name);
  const summary =
    value.technicians.length === 0
      ? 'Everyone'
      : names.length > 0 && names.length <= 2
        ? names.join(', ')
        : `${value.technicians.length} technicians`;

  return (
    <div className="my-5 grid gap-3">
      <div role="group" aria-label="Status" className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-sm font-medium text-ink-muted">Status</span>
        {JOB_STATUSES.map((s) => {
          const on = value.statuses.includes(s);
          return (
            <button
              key={s}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(toggleStatus(value, s))}
              className={`inline-flex min-h-9 items-center gap-1.5 rounded-full border-[1.5px] px-3 text-sm font-semibold ${
                on ? 'border-brand bg-brand-soft text-brand-ink' : 'border-line-strong bg-surface hover:bg-canvas'
              }`}
            >
              <StatusPin status={s} size={16} />
              {STATUS_META[s].label}
            </button>
          );
        })}
        {value.statuses.length === 0 && <span className={ui.muted}>(showing all)</span>}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className={ui.label}>
          Day
          <input className={ui.input} type="date" value={value.date} onChange={(e) => onChange({ ...value, date: e.target.value })} />
        </label>
        <div className={ui.label}>
          Technicians
          <details className="relative">
            <summary className={`${ui.input} flex min-w-52 cursor-pointer list-none items-center justify-between gap-3`}>
              <span>{summary}</span>
              <span aria-hidden="true">▾</span>
            </summary>
            <div className="absolute z-[1000] mt-1 grid max-h-64 min-w-full gap-1 overflow-auto rounded-xl border border-line bg-surface p-2 shadow-lg">
              {technicians.length === 0 && <span className={ui.muted}>No technicians yet.</span>}
              {technicians.map((t) => (
                <label key={t.id} className="flex min-h-9 cursor-pointer items-center gap-2 rounded-lg px-2 hover:bg-canvas">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand"
                    checked={value.technicians.includes(String(t.id))}
                    onChange={() => onChange(toggleTechnician(value, String(t.id)))}
                  />
                  {t.user.full_name}
                </label>
              ))}
            </div>
          </details>
        </div>
        {hasFilters(value) && (
          <button type="button" className={ui.btnSmall} onClick={onClear}>Clear filters</button>
        )}
      </div>
    </div>
  );
}
