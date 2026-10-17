import { useAuth } from '../../auth/useAuth';
import { ui } from '../../shared/ui';

// Placeholder until jobs exist (S1-3 / Sprint 2 technician view).
export default function TechnicianHome() {
  const { user } = useAuth();
  return (
    <section className={ui.card}>
      <h1 className={ui.h1}>Hello, {user?.full_name}</h1>
      <p className={ui.muted}>Your assigned jobs will appear here.</p>
    </section>
  );
}