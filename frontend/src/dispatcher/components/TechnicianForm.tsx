import { useEffect, useState, type FormEvent } from 'react';
import { createUser, fetchSkills, updateTechnician, type Skill } from '../../shared/api/client';
import { ApiError } from '../../shared/api/http';
import type { Technician } from '../../shared/api/models';
import { ui } from '../../shared/ui';

const hhmm = (t: string) => t.slice(0, 5);

interface Props {
  /** Present = edit this technician; absent = create a new one. */
  technician?: Technician;
  onDone: () => void;
  onCancel: () => void;
}

export default function TechnicianForm({ technician, onDone, onCancel }: Props) {
  const editing = technician !== undefined;
  const [skills, setSkills] = useState<Skill[]>([]);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState(technician?.phone ?? '');
  const [shiftStart, setShiftStart] = useState(technician ? hhmm(technician.shift_start) : '08:00');
  const [shiftEnd, setShiftEnd] = useState(technician ? hhmm(technician.shift_end) : '17:00');
  const [skillIds, setSkillIds] = useState<number[]>(technician?.skills.map((s) => s.id) ?? []);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchSkills().then(setSkills).catch(() => setSkills([]));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (skillIds.length === 0) {
      setErrors({ skill_ids: 'Select at least one skill.' });
      return;
    }
    setBusy(true);
    setErrors({});
    try {
      if (technician) {
        await updateTechnician(technician.id, {
          shift_start: shiftStart,
          shift_end: shiftEnd,
          phone: phone.trim() === '' ? null : phone.trim(),
          skill_ids: skillIds,
        });
      } else {
        // TIME: creating goes through POST /users/ (which has no phone field);
        // phone is added afterwards with Edit. Full-fidelity: accept phone there.
        await createUser({
          email,
          password,
          full_name: fullName,
          role: 'technician',
          technician: { shift_start: shiftStart, shift_end: shiftEnd, skill_ids: skillIds },
        });
      }
      onDone();
    } catch (err) {
      setErrors(
        err instanceof ApiError
          ? { ...err.fieldErrors, _: err.message }
          : { _: 'Could not reach the server.' },
      );
    } finally {
      setBusy(false);
    }
  }

  const fieldError = (k: string) => errors[k] && <span className={ui.error}>{errors[k]}</span>;
  // Show the summary line only when no field-level message already explains it.
  const showSummary = errors._ && !Object.keys(errors).some((k) => k !== '_');

  return (
    <form onSubmit={onSubmit} className={`${ui.form} mb-6 rounded-md border border-slate-200 p-4`}>
      <h2 className="text-lg font-semibold">
        {editing ? `Edit ${technician.user.full_name}` : 'Add a technician'}
      </h2>

      {!editing && (
        <>
          <label className={ui.label}>
            Full name
            <input className={ui.input} value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            {fieldError('full_name')}
          </label>
          <label className={ui.label}>
            Email
            <input className={ui.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            {fieldError('email')}
          </label>
          <label className={ui.label}>
            Temporary password
            <input className={ui.input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
            {fieldError('password')}
          </label>
        </>
      )}

      <div className={ui.row}>
        <label className={ui.label}>
          Shift starts
          <input className={ui.input} type="time" value={shiftStart} onChange={(e) => setShiftStart(e.target.value)} required />
          {fieldError('shift_start')}
        </label>
        <label className={ui.label}>
          Shift ends
          <input className={ui.input} type="time" value={shiftEnd} onChange={(e) => setShiftEnd(e.target.value)} required />
          {fieldError('shift_end')}
        </label>
      </div>

      {editing && (
        <label className={ui.label}>
          Phone
           <input
            className={ui.input}
            type="tel"
            inputMode="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            maxLength={20}
            pattern="\+?[0-9\s().\-]{7,20}"
            title="Digits, spaces, + ( ) - . only, e.g. +1 (555) 123-4567"
           />
          {fieldError('phone')}
        </label>
      )}

      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium text-slate-700">Skills</legend>
        <div className="flex flex-wrap gap-2">
          {skills.map((s) => (
            <label key={s.id} className="flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-sm">
              <input
                type="checkbox"
                checked={skillIds.includes(s.id)}
                onChange={(e) =>
                  setSkillIds(e.target.checked ? [...skillIds, s.id] : skillIds.filter((x) => x !== s.id))
                }
              />
              {s.name}
            </label>
          ))}
        </div>
        {fieldError('skill_ids')}
      </fieldset>

      {showSummary && <p role="alert" className={ui.error}>{errors._}</p>}
      {errors.non_field_errors && <p role="alert" className={ui.error}>{errors.non_field_errors}</p>}

      <div className="flex gap-2">
        <button className={ui.btn} disabled={busy}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Add technician'}</button>
        <button type="button" className={ui.btnSmall} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}