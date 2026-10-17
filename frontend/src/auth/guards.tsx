import { Navigate, Outlet, useLocation } from 'react-router-dom';
import type { Role } from '../shared/api/models';
import { ui } from '../shared/ui'; 
import { homeFor } from './homeFor';
import { useAuth } from './useAuth';

/** Everything behind this needs a signed-in user. */
export function RequireAuth() {
  const { user } = useAuth();
  const location = useLocation();
  if (user === undefined) return <p className={ui.centerNote}>Loading…</p>;
  if (user === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <Outlet />;
}

/** Wrong role -> bounce to that role's own home (the API enforces it too). */
export function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth();
  if (!user) return null; // RequireAuth above handles this
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}

/** Login/register pages: signed-in users go straight to their home. */
export function PublicOnly() {
  const { user } = useAuth();
  if (user === undefined) return <p className={ui.centerNote}>Loading…</p>;
  if (user) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}

export function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={user ? homeFor(user.role) : '/login'} replace />;
}