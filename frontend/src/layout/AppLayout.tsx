import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { ROLE_LABEL } from '../shared/api/models';
import { ui } from '../shared/ui';

const link = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'font-semibold text-blue-600' : 'text-slate-600 hover:text-slate-900';

export default function AppLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  const staff = user.role !== 'technician';

  return (
    <div className={ui.page}>
      <header className="flex flex-wrap items-center gap-5 border-b border-slate-200 bg-white px-6 py-3">
        <strong>{user.organization.name}</strong>
        <nav className="flex flex-1 gap-4">
          {staff && <NavLink to="/dashboard" className={link}>Dashboard</NavLink>}
          {!staff && <NavLink to="/tech" className={link}>My jobs</NavLink>}
          {staff && <NavLink to="/organization" className={link}>Organization</NavLink>}
          {user.role === 'head_dispatcher' && <NavLink to="/users" className={link}>Team</NavLink>}
        </nav>
        <span className="text-sm text-slate-500">
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
      <div className="mx-auto my-6 max-w-5xl px-4">
        <Outlet />
      </div>
    </div>
  );
}