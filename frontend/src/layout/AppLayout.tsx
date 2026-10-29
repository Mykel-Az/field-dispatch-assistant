import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { ROLE_LABEL } from '../shared/api/models';
import { ui } from '../shared/ui';

const link = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-full px-4 py-2 font-medium ${
    isActive ? 'bg-brand-soft font-bold text-brand-ink' : 'text-ink-muted hover:text-ink'
  }`;

export default function AppLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  const staff = user.role !== 'technician';

  return (
    <div className={ui.page}>
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <span aria-hidden="true" className="size-8 rounded-[10px] bg-brand" />
          <strong className="text-lg">{user.organization.name}</strong>
        </div>
        <nav className="order-last flex w-full flex-nowrap gap-1.5 overflow-x-auto sm:order-none sm:w-auto sm:flex-1 sm:flex-wrap sm:overflow-visible">
          {staff && <NavLink to="/dashboard" className={link}>Dashboard</NavLink>}
          {staff && <NavLink to="/jobs" className={link}>Jobs</NavLink>}
          {!staff && <NavLink to="/tech" className={link}>My jobs</NavLink>}
          {staff && <NavLink to="/technicians" className={link}>Technicians</NavLink>}
          {staff && <NavLink to="/organization" className={link}>Organization</NavLink>}
          {user.role === 'head_dispatcher' && <NavLink to="/users" className={link}>Team</NavLink>}
        </nav>
        <span className="text-sm text-ink-muted">
          {user.full_name} · {ROLE_LABEL[user.role]}
        </span>
        <button
          className={ui.btnSmall}
          onClick={async () => {
            await signOut();
            navigate('/login', { replace: true });
          }}
        >
          Sign out
        </button>
      </header>
      <div className="mx-auto my-4 max-w-6xl px-4 pb-10">
        <Outlet />
      </div>
    </div>
  );
}
