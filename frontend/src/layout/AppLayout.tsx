import { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { ROLE_LABEL } from '../shared/api/models';
import { initOrgTimezone } from '../shared/jobTime';
import { useOrgTimezone } from '../shared/useOrgTimezone';
import { ui } from '../shared/ui';
import NavDrawer from './NavDrawer';
import { navItems } from './navItems';

const link = ({ isActive }: { isActive: boolean }) =>
  `block rounded-xl px-4 py-3 font-medium ${
    isActive ? 'bg-brand-soft font-bold text-brand-ink' : 'text-ink-muted hover:bg-canvas hover:text-ink'
  }`;

function Brand({ name, wrap = false }: { name: string; wrap?: boolean }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <span aria-hidden="true" className="size-8 shrink-0 rounded-[10px] bg-brand" />
      <strong className={`text-lg leading-tight ${wrap ? 'break-words' : 'truncate'}`}>{name}</strong>
    </div>
  );
}

/**
 * Staff get a sidebar on large screens (1024px and up) and a menu button with a
 * drawer below that. A technician has one page, so they get a plain top bar with
 * no menu at any size.
 */
export default function AppLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // The drawer is open for one location only: moving to another page closes it,
  // with no effect needed to do so.
  const [openAt, setOpenAt] = useState<string | null>(null);
  useOrgTimezone(); // re-render the layout (and its pages) when the zone changes
  if (!user) return null;
  // Set before the pages render, so their first paint already uses the org's clock.
  initOrgTimezone(user.organization.timezone);

  const items = navItems(user.role);
  const hasMenu = items.length > 1;
  const open = openAt === location.key;
  const close = () => setOpenAt(null);

  async function leave() {
    await signOut();
    navigate('/login', { replace: true });
  }

  const nav = (
    <nav aria-label="Main" className="grid gap-1">
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} className={link}>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
  const account = (
    <div className="grid gap-2">
      <span className="text-sm text-ink-muted">
        {user.full_name} · {ROLE_LABEL[user.role]}
      </span>
      <button className={ui.btnSmall} onClick={leave}>Sign out</button>
    </div>
  );

  return (
    <div className={`${ui.page} ${hasMenu ? 'lg:flex' : ''}`}>
      {hasMenu && (
        <aside className="hidden w-60 shrink-0 flex-col justify-between gap-6 border-r border-line bg-surface p-4 lg:sticky lg:top-0 lg:flex lg:h-screen">
          <div className="grid gap-6">
            <Brand name={user.organization.name} wrap />
            {nav}
          </div>
          {account}
        </aside>
      )}

      <div className="min-w-0 flex-1">
        <header
          className={`sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-canvas px-4 py-2 ${hasMenu ? 'lg:hidden' : ''}`}
        >
          {hasMenu && (
            <button
              type="button"
              className="grid size-11 shrink-0 place-items-center rounded-xl border-[1.5px] border-line-strong bg-surface"
              aria-label="Open menu"
              aria-expanded={open}
              onClick={() => setOpenAt(location.key)}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M3 5h14M3 10h14M3 15h14" />
              </svg>
            </button>
          )}
          <div className="min-w-0 flex-1">
            <Brand name={user.organization.name} />
          </div>
          {!hasMenu && (
            <>
              <span className="hidden text-sm text-ink-muted sm:inline">
                {user.full_name} · {ROLE_LABEL[user.role]}
              </span>
              <button className={ui.btnSmall} onClick={leave}>Sign out</button>
            </>
          )}
        </header>

        <main className="mx-auto my-4 max-w-6xl px-4 pb-10">
          <Outlet />
        </main>
      </div>

      {open && (
        <NavDrawer onClose={close}>
          <div className="flex items-center justify-between gap-2">
            <Brand name={user.organization.name} wrap />
            <button type="button" className={ui.btnSmall} onClick={close}>Close</button>
          </div>
          {nav}
          <div className="mt-auto">{account}</div>
        </NavDrawer>
      )}
    </div>
  );
}
