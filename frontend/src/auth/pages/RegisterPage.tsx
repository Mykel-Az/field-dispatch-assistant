import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError } from '../../shared/api/http';
import { ui } from '../../shared/ui';
import { homeFor } from '../homeFor';
import { useAuth } from '../useAuth';

export default function RegisterPage() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ organization_name: '', full_name: '', email: '', password: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    try {
      const user = await signUp(form);
      navigate(homeFor(user.role), { replace: true });
    } catch (err) {
      setErrors(err instanceof ApiError ? { ...err.fieldErrors, _: err.message } : { _: 'Could not reach the server.' });
    } finally {
      setBusy(false);
    }
  }

    const field = (k: keyof typeof form, label: string, type = 'text', auto?: string) => (
    <label className={ui.label}>
      {label}
      <input className={ui.input} type={type} value={form[k]} onChange={set(k)} required autoComplete={auto} />
      {errors[k] && <span className={ui.error}>{errors[k]}</span>}
    </label>
  );

  return (
    <main className={ui.cardNarrow}>
      <h1 className={ui.h1}>Create your organization</h1>
      <p className={`${ui.muted} mb-4`}>You become the head dispatcher and can add your team afterwards.</p>
      <form onSubmit={onSubmit} className={ui.form}>
        {field('organization_name', 'Company name')}
        {field('full_name', 'Your full name', 'text', 'name')}
        {field('email', 'Email', 'email', 'username')}
        {field('password', 'Password', 'password', 'new-password')}
        {errors._ && !Object.keys(errors).some((k) => k !== '_') && <p role="alert" className={ui.error}>{errors._}</p>}
        <button className={ui.btn} disabled={busy}>{busy ? 'Creating…' : 'Create organization'}</button>
      </form>
      <p className="mt-4 text-sm">
        Already registered? <Link className="text-blue-600 hover:underline" to="/login">Sign in</Link>
      </p>
    </main>
  );
}