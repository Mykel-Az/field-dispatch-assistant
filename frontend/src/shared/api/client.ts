import type { components } from './schema';
import { get, patch, post } from './http';
import type {
  CreateUserInput,
  Organization,
  Page,
  RegisterInput,
  User,
} from './models';

export type Skill = components['schemas']['Skill'];
export type Health = components['schemas']['Health'];

export const checkHealth = () => get<Health>('/health/');
export const fetchSkills = () => get<Skill[]>('/skills/');

// --- auth ---
export const fetchMe = () => get<User>('/auth/me/', { skipUnauthorizedHandler: true });
export const login = (email: string, password: string) =>
  post<User>('/auth/login/', { email, password });
export const register = (input: RegisterInput) => post<User>('/auth/register/', input);
export const logout = () => post<void>('/auth/logout/');

// --- users (head dispatcher only) ---
export interface UserFilters {
  role?: string;
  is_active?: string;
}
export const fetchUsers = (filters: UserFilters = {}) => {
  const params = new URLSearchParams();
  if (filters.role) params.set('role', filters.role);
  if (filters.is_active) params.set('is_active', filters.is_active);
  const qs = params.toString();
  return get<Page<User>>(`/users/${qs ? `?${qs}` : ''}`);
};
export const createUser = (input: CreateUserInput) => post<User>('/users/', input);
export const deactivateUser = (id: number) => post<User>(`/users/${id}/deactivate/`);
export const reactivateUser = (id: number) => post<User>(`/users/${id}/reactivate/`);

// --- organization ---
export const fetchOrganization = () => get<Organization>('/organization/');
export const updateOrganization = (
  input: Partial<Omit<Organization, 'id' | 'geocode_status' | 'is_configured'>> & {
    version: number;
  },
) => patch<Organization>('/organization/', input);