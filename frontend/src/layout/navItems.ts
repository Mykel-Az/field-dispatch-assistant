import type { Role } from '../shared/api/models';

export interface NavItem {
  to: string;
  label: string;
}

/** What each role can open. One list feeds the sidebar and the drawer, so they never differ. */
export function navItems(role: Role): NavItem[] {
  if (role === 'technician') return [{ to: '/tech', label: 'My jobs' }];
  const items: NavItem[] = [
    { to: '/dashboard', label: 'Dashboard' },
    { to: '/jobs', label: 'Jobs' },
    { to: '/plan', label: 'Plan' },
    { to: '/map', label: 'Map' },
    { to: '/technicians', label: 'Technicians' },
    { to: '/organization', label: 'Organization' },
  ];
  if (role === 'head_dispatcher') items.push({ to: '/users', label: 'Team' });
  return items;
}
