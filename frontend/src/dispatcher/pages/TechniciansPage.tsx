import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../auth/useAuth';
import { deactivateUser, fetchTechnicians, reactivateUser } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { Technician } from '../../shared/api/models';
import {
  HeadCell,
  StackedBody,
  StackedCell,
  StackedHead,
  StackedRow,
  StackedTable,
} from '../../shared/components/StackedTable';
import { ui } from '../../shared/ui';
import TechnicianForm from '../components/TechnicianForm';

const hhmm = (t: string) => t.slice(0, 5);

export default function TechniciansPage() {
  const { user } = useAuth();
  const canManage = user?.role === 'head_dispatcher';
  const [technicians, setTechnicians] = useState<Technician[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  // undefined = form closed, null = creating, Technician = editing that one
  const [formFor, setFormFor] = useState<Technician | null | undefined>(undefined);

  const load = useCallback(async () => {
    try {
      setTechnicians(await fetchTechnicians());
      setLoadError('');
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : 'Could not load technicians.');
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetch on mount
    void load();
  }, [load]);

  async function toggleActive(t: Technician) {
    setActionError('');
    try {
      await (t.user.is_active ? deactivateUser(t.user.id) : reactivateUser(t.user.id));
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Action failed.');
    }
  }

  return (
    <section className={ui.card}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Technicians</h1>
        {canManage && formFor === undefined && (
          <button className={ui.btn} onClick={() => setFormFor(null)}>Add technician</button>
        )}
      </div>

      {formFor !== undefined && (
        <TechnicianForm
          // a new key resets the form's state when switching between technicians
          key={formFor?.id ?? 'new'}
          technician={formFor ?? undefined}
          onCancel={() => setFormFor(undefined)}
          onDone={() => {
            setFormFor(undefined);
            void load();
          }}
        />
      )}

      {loadError && <p role="alert" className={ui.error}>{loadError}</p>}
      {actionError && <p role="alert" className={ui.error}>{actionError}</p>}
      {technicians === null && !loadError && <p className={ui.muted}>Loading…</p>}
      {technicians?.length === 0 && (
        <p className={ui.muted}>
          No technicians yet.{canManage ? ' Add one to start planning jobs.' : ''}
        </p>
      )}

      {technicians && technicians.length > 0 && (
        <StackedTable label="Technicians">
          <StackedHead>
            <HeadCell>Name</HeadCell>
            <HeadCell>Shift</HeadCell>
            <HeadCell>Skills</HeadCell>
            <HeadCell>Phone</HeadCell>
            <HeadCell>Status</HeadCell>
            {canManage && <HeadCell />}
          </StackedHead>
          <StackedBody>
            {technicians.map((t) => (
              <StackedRow key={t.id} muted={!t.user.is_active}>
                <StackedCell label="Name">
                  <div className="min-w-0">
                    <div className="font-medium">{t.user.full_name}</div>
                    <div className="break-all text-xs text-ink-muted">{t.user.email}</div>
                  </div>
                </StackedCell>
                <StackedCell label="Shift">
                  <span className="whitespace-nowrap">{hhmm(t.shift_start)}–{hhmm(t.shift_end)}</span>
                </StackedCell>
                <StackedCell label="Skills">
                  {t.skills.length === 0 ? (
                    <span className="text-ink-muted">none</span>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {t.skills.map((s) => (
                        <span key={s.id} className="rounded-full bg-brand-soft px-2 py-0.5 text-xs text-brand-ink">{s.name}</span>
                      ))}
                    </div>
                  )}
                </StackedCell>
                <StackedCell label="Phone">{t.phone || '—'}</StackedCell>
                <StackedCell label="Status">{t.user.is_active ? 'Active' : 'Deactivated'}</StackedCell>
                {canManage && (
                  <StackedCell actions>
                    <button className={ui.btnSmall} onClick={() => setFormFor(t)}>Edit</button>
                    <button className={ui.btnSmall} onClick={() => toggleActive(t)}>
                      {t.user.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </StackedCell>
                )}
              </StackedRow>
            ))}
          </StackedBody>
        </StackedTable>
      )}
    </section>
  );
}