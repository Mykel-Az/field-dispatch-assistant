import type { Role } from '../shared/api/models';

export const homeFor = (role: Role) => (role === 'technician' ? '/tech' : '/dashboard');