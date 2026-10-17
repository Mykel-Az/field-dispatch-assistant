import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../../shared/api/http';
import { ui } from '../../shared/ui';
import { homeFor } from '../homeFor';
import { useAuth } from '../useAuth';

export default function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const user = await signIn(email, password);
      navigate(from ?? homeFor(user.role), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.');
    } finally {
      setBusy(false);
    }
  }

    return (
    <main className={ui.cardNarrow}>
      <h1 className={ui.h1}>Sign in</h1>
      <form onSubmit={onSubmit} className={ui.form}>
        <label className={ui.label}>
          Email
          <input className={ui.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
        </label>
        <label className={ui.label}>
          Password
          <input className={ui.input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        </label>
        {error && <p role="alert" className={ui.error}>{error}</p>}
        <button className={ui.btn} disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <p className="mt-4 text-sm">
        New company? <Link className="text-blue-600 hover:underline" to="/register">Create an organization</Link>
      </p>
    </main>
  );
}