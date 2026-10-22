import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../auth/useAuth';
import { deactivateUser, fetchTechnicians, reactivateUser } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { Technician } from '../../shared/api/models';
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
      <div className="mb-4 flex items-center justify-between">
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
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-slate-500">
              <th className="p-2">Name</th>
              <th className="p-2">Shift</th>
              <th className="p-2">Skills</th>
              <th className="p-2">Phone</th>
              <th className="p-2">Status</th>
              {canManage && <th />}
            </tr>
          </thead>
          <tbody>
            {technicians.map((t) => (
              <tr key={t.id} className={`border-b border-slate-100 ${t.user.is_active ? '' : 'text-slate-400'}`}>
                <td className="p-2">
                  <div className="font-medium">{t.user.full_name}</div>
                  <div className="text-xs text-slate-500">{t.user.email}</div>
                </td>
                <td className="p-2 whitespace-nowrap">{hhmm(t.shift_start)}–{hhmm(t.shift_end)}</td>
                <td className="p-2">
                  {t.skills.length === 0 ? (
                    <span className="text-slate-400">none</span>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {t.skills.map((s) => (
                        <span key={s.id} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{s.name}</span>
                      ))}
                    </div>
                  )}
                </td>
                <td className="p-2">{t.phone || '—'}</td>
                <td className="p-2">{t.user.is_active ? 'Active' : 'Deactivated'}</td>
                {canManage && (
                  <td className="p-2 text-right whitespace-nowrap">
                    <button className={`${ui.btnSmall} mr-2`} onClick={() => setFormFor(t)}>Edit</button>
                    <button className={ui.btnSmall} onClick={() => toggleActive(t)}>
                      {t.user.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}