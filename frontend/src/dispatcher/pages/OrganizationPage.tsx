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
  const [form, setForm] = useState({ name: '', email: '', phone: '', address: '', lat: '', lng: '', work_start: '', work_end: '', timezone: 'America/Chicago', max_jobs: '3', strategy: 'balanced' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  function apply(o: Organization) {
    setOrg(o);
    setForm({
      name: o.name, email: o.email ?? '', phone: o.phone ?? '', address: o.address ?? '',
      lat: o.lat === null ? '' : String(o.lat), lng: o.lng === null ? '' : String(o.lng),
      work_start: hhmm(o.work_start), work_end: hhmm(o.work_end), timezone: o.timezone,
      max_jobs: String(o.max_jobs_per_tech_per_day), strategy: o.scoring_strategy,
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
        max_jobs_per_tech_per_day: Number(form.max_jobs),
        scoring_strategy: form.strategy as Organization['scoring_strategy'],
      });
      apply(saved);
      setOrgTimezone(saved.timezone); // every screen redraws its times on the new clock
      // Keep the signed-in user's copy in step, or the next render would restore the old zone.
      await refreshUser().catch(() => undefined);
      setMessage('Saved.');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && (err.body as { code?: string })?.code === 'timezone_locked') {
        // The server's message says how many jobs are in the way. The form keeps the user's edit; the
        // saved zone (and every screen's clock) is unchanged.
        setErrors({ timezone: err.message });
      } else if (err instanceof ApiError && err.status === 409) {
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
            Every job time and working hour is on this clock, whatever zone your computer is in. It cannot be
            changed while a job is assigned or in progress.
          </span>
          {errors.timezone && <span role="alert" className={ui.error}>{errors.timezone}</span>}
        </label>
        <div className={ui.row}>
          {f('work_start', 'Working day starts', 'time')}
          {f('work_end', 'Working day ends', 'time')}
        </div>
        <h2 className={ui.h2}>Planning</h2>
        <label className={ui.label}>
          Most jobs per technician per day
          <input
            className={ui.input}
            type="number"
            min={1}
            max={10}
            step={1}
            value={form.max_jobs}
            disabled={!canEdit}
            onChange={(e) => setForm({ ...form, max_jobs: e.target.value })}
          />
          <span className="text-sm font-normal text-ink-muted">
            The planner never gives a technician more than this on one day. Urgent jobs can go over it when no one
            else can take them in time. Assigning by hand is not limited, but warns you.
          </span>
          {errors.max_jobs_per_tech_per_day && <span className={ui.error}>{errors.max_jobs_per_tech_per_day}</span>}
        </label>
        <label className={ui.label}>
          How the planner chooses a technician
          <select
            className={ui.input}
            value={form.strategy}
            disabled={!canEdit}
            onChange={(e) => setForm({ ...form, strategy: e.target.value })}
          >
            <option value="balanced">Balanced: shorter drives, even workload, on-time arrivals</option>
            <option value="nearest">Nearest: the closest technician who can make it</option>
          </select>
          {errors.scoring_strategy && <span className={ui.error}>{errors.scoring_strategy}</span>}
        </label>
        {errors._ && <p role="alert" className={ui.error}>{errors._}</p>}
        {message && <p role="status">{message}</p>}
        {canEdit ? <button className={ui.btn} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button> : <p className={ui.muted}>Only a head dispatcher can edit these settings.</p>}
      </form>
    </section>
  );
}