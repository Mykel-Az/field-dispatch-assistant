import { useEffect, useState, type FormEvent } from 'react';
import { useAuth } from '../../auth/useAuth';
import { fetchOrganization, updateOrganization } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import { US_TIMEZONES, type Organization } from '../../shared/api/models';
import { setOrgTimezone } from '../../shared/jobTime';
import { ui } from '../../shared/ui';

const hhmm = (t: string | null) => (t ? t.slice(0, 5) : '');
const num = (s: string) => (s.trim() === '' ? null : Number(s));

export default function OrganizationPage() {
  const { user, refreshUser } = useAuth();
  const canEdit = user?.role === 'head_dispatcher';
  const [org, setOrg] = useState<Organization | null>(null);
  const [form, setForm] = useState({ name: '', email: '', phone: '', address: '', lat: '', lng: '', work_start: '', work_end: '', timezone: 'America/Chicago' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  function apply(o: Organization) {
    setOrg(o);
    setForm({
      name: o.name, email: o.email ?? '', phone: o.phone ?? '', address: o.address ?? '',
      lat: o.lat === null ? '' : String(o.lat), lng: o.lng === null ? '' : String(o.lng),
      work_start: hhmm(o.work_start), work_end: hhmm(o.work_end), timezone: o.timezone,
    });
  }

  useEffect(() => {
    fetchOrganization().then(apply).catch((e) => setErrors({ _: e instanceof ApiError ? e.message : 'Could not load.' }));
  }, []);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!org) return;
    setBusy(true);
    setErrors({});
    setMessage('');
    try {
      const saved = await updateOrganization({
        version: org.version,
        name: form.name,
        email: form.email,
        phone: form.phone,
        address: form.address,
        lat: num(form.lat),
        lng: num(form.lng),
        work_start: form.work_start || null,
        work_end: form.work_end || null,
        timezone: form.timezone,
      });
      apply(saved);
      setOrgTimezone(saved.timezone); // every screen redraws its times on the new clock
      // Keep the signed-in user's copy in step, or the next render would restore the old zone.
      await refreshUser().catch(() => undefined);
      setMessage('Saved.');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Someone else saved first: show their version, keep the user informed. Race condition/concurrency
        setErrors({ _: 'Someone else changed these settings. The latest values are loaded; re-apply your edit.' });
        fetchOrganization().then(apply).catch(() => undefined);
      } else {
        setErrors(err instanceof ApiError ? { ...err.fieldErrors, _: err.message } : { _: 'Could not reach the server.' });
      }
    } finally {
      setBusy(false);
    }
  }

  if (!org) return <p className={ui.centerNote}>{errors._ || 'Loading…'}</p>;

  const f = (k: keyof typeof form, label: string, type = 'text', extra: object = {}) => (
    <label className={ui.label}>
      {label}
      <input className={ui.input} type={type} value={form[k]} disabled={!canEdit} onChange={(e) => setForm({ ...form, [k]: e.target.value })} {...extra} />
      {errors[k] && <span className={ui.error}>{errors[k]}</span>}
    </label>
  );

  return (
    <section className={ui.card}>
      <h1 className={ui.h1}>Organization</h1>
      {!org.is_configured && (
        <p className={`${ui.notice} mb-4`}>Finish setting up: add the office address, location and working hours so jobs can be scheduled.</p>
      )}
      <form onSubmit={onSave} className={ui.form}>
        {f('name', 'Company name')}
        {f('email', 'Contact email', 'email')}
        {f('phone', 'Phone')}
        {f('address', 'Address')}
        <div className={ui.row}>
          {f('lat', 'Latitude', 'number', { step: 'any', min: -90, max: 90 })}
          {f('lng', 'Longitude', 'number', { step: 'any', min: -180, max: 180 })}
        </div>
        <p className={ui.muted}>Location status: {org.geocode_status}. Coordinates entered here are saved as “manual”.</p>
        <label className={ui.label}>
          Time zone
          <select
            className={ui.input}
            value={form.timezone}
            disabled={!canEdit}
            onChange={(e) => setForm({ ...form, timezone: e.target.value })}
          >
            {US_TIMEZONES.map((z) => (
              <option key={z.value} value={z.value}>{z.label}</option>
            ))}
          </select>
          <span className="text-sm font-normal text-ink-muted">
            Every job time and working hour is on this clock, whatever zone your computer is in.
          </span>
        </label>
        <div className={ui.row}>
          {f('work_start', 'Working day starts', 'time')}
          {f('work_end', 'Working day ends', 'time')}
        </div>
        {errors._ && <p role="alert" className={ui.error}>{errors._}</p>}
        {message && <p role="status">{message}</p>}
        {canEdit ? <button className={ui.btn} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button> : <p className={ui.muted}>Only a head dispatcher can edit these settings.</p>}
      </form>
    </section>
  );
}