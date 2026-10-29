import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useAuth } from '../../auth/useAuth';
import {
  createUser,
  deactivateUser,
  fetchUsers,
  reactivateUser,
} from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import { ui } from '../../shared/ui';
import { ROLE_LABEL, type CreateUserInput, type Role, type User } from '../../shared/api/models';

const EMPTY = { email: '', password: '', full_name: '', role: 'dispatcher' as Role };

export default function UsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [count, setCount] = useState(0);
  const [roleFilter, setRoleFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [form, setForm] = useState(EMPTY);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const page = await fetchUsers({ role: roleFilter, is_active: activeFilter });
      setUsers(page.results);
      setCount(page.count);
      setLoadError('');
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : 'Could not load users.');
    }
  }, [roleFilter, activeFilter]);


  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetch on mount/filter change
    void load();
  }, [load]);
  

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormErrors({});
    const input: CreateUserInput = {
      email: form.email,
      password: form.password,
      full_name: form.full_name,
      role: form.role,
    };
    try {
      await createUser(input);
      setForm(EMPTY);
      await load();
    } catch (err) {
      setFormErrors(err instanceof ApiError ? { ...err.fieldErrors, _: err.message } : { _: 'Could not reach the server.' });
    } finally {
      setBusy(false);
    }
  }

  async function toggle(u: User) {
    setActionError('');
    try {
      await (u.is_active ? deactivateUser(u.id) : reactivateUser(u.id));
      await load();
    } catch (err) {
      // 409 last_head arrives as a readable message from the API.
      setActionError(err instanceof ApiError ? err.message : 'Action failed.');
    }
  }

  const err = (k: string) => formErrors[k] && <span className={ui.error}>{formErrors[k]}</span>;

  return (
    <section className={ui.card}>
      <h1 className={ui.h1}>Team</h1>

      <div className={ui.row}>
        <label className={ui.label}>
          Role
          <select className={ui.input} value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">All</option>
            {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
              <option key={r} value={r}>{ROLE_LABEL[r]}</option>
            ))}
          </select>
        </label>
        <label className={ui.label}>
          Status
          <select className={ui.input} value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)}>
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Deactivated</option>
          </select>
        </label>
      </div>

      {loadError && <p role="alert" className={`${ui.error} mt-3`}>{loadError}</p>}
      {actionError && <p role="alert" className={`${ui.error} mt-3`}>{actionError}</p>}

      <table className="my-4 w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line text-ink-muted"><th className="p-2">Name</th><th className="p-2">Email</th><th className="p-2">Role</th><th className="p-2">Status</th><th /></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className={`border-b border-line ${u.is_active ? '' : 'text-ink-muted'}`}>
              <td className="p-2">{u.full_name}</td>
              <td className="p-2">{u.email}</td>
              <td className="p-2">{ROLE_LABEL[u.role]}</td>
              <td className="p-2">{u.is_active ? 'Active' : 'Deactivated'}</td>
              <td className="p-2 text-right">
                {u.id !== me?.id && (
                  <button className={ui.btnSmall} onClick={() => toggle(u)}>{u.is_active ? 'Deactivate' : 'Reactivate'}</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {/* TIME: first page only (50). Full-fidelity: next/previous paging. */}
      {count > users.length && <p className={ui.muted}>Showing {users.length} of {count}.</p>}

      <h2 className={ui.h2}>Add a team member</h2>
      <form onSubmit={onCreate} className={ui.form}>
        <label className={ui.label}>Full name<input className={ui.input} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />{err('full_name')}</label>
        <label className={ui.label}>Email<input className={ui.input} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />{err('email')}</label>
        <label className={ui.label}>Temporary password<input className={ui.input} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required autoComplete="new-password" />{err('password')}</label>
        <label className={ui.label}>
          Role
          <select className={ui.input} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            {(Object.keys(ROLE_LABEL) as Role[]).filter((r) => r !== 'technician').map((r) => (
              <option key={r} value={r}>{ROLE_LABEL[r]}</option>
            ))}
          </select>
          {err('role')}
        </label>

        
        {formErrors._ && !Object.keys(formErrors).some((k) => k !== '_') && <p role="alert" className={ui.error}>{formErrors._}</p>}
        <button className={ui.btn} disabled={busy}>{busy ? 'Adding…' : 'Add member'}</button>
      </form>
    </section>
  );
}