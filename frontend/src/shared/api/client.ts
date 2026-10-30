import { filterQuery, NO_FILTERS, type JobFilterValues } from '../filters';
import type { components } from './schema';
import { get, patch, post } from './http';
import type {
  CreateUserInput,
  JobCreateInput,
  JobDetail,
  JobRow,
  JobUpdateInput,
  Organization,
  Page,
  RegisterInput,
  User,
  Technician,
  TechnicianUpdate,
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

// --- technicians ---
export const fetchTechnicians = () => get<Technician[]>('/technicians/');
export const updateTechnician = (id: number, input: TechnicianUpdate) =>
  patch<Technician>(`/technicians/${id}/`, input);

// --- jobs (dispatcher and head dispatcher) ---
export const fetchJobs = (filters: JobFilterValues = NO_FILTERS, page = 1) => {
  const params = filterQuery(filters);
  if (page > 1) params.set('page', String(page));
  const qs = params.toString();
  return get<Page<JobRow>>(`/jobs/${qs ? `?${qs}` : ''}`);
};
export const fetchJob = (id: number) => get<JobDetail>(`/jobs/${id}/`);
export const createJob = (input: JobCreateInput) => post<JobDetail>('/jobs/', input);
export const updateJob = (id: number, input: JobUpdateInput) =>
  patch<JobDetail>(`/jobs/${id}/`, input);
export const cancelJob = (id: number, reason: string) =>
  post<JobDetail>(`/jobs/${id}/cancel/`, { reason });
export const assignJob = (id: number, technicianId: number, version: number) =>
  post<JobDetail>(`/jobs/${id}/assign/`, { technician_id: technicianId, version });
export const unassignJob = (id: number, version: number) =>
  post<JobDetail>(`/jobs/${id}/unassign/`, { version });

export interface AddressCheck {
  status: 'ok' | 'approximate' | 'failed' | 'pending' | 'manual';
  lat: number | null;
  lng: number | null;
  label: string;
}
export const lookupAddress = (address: string, postalCode: string) =>
  post<AddressCheck>('/geocode/lookup/', { address, postal_code: postalCode });
export const pinJob = (id: number, lat: number, lng: number, version: number) =>
  post<JobDetail>(`/jobs/${id}/location/`, { lat, lng, version });
export const retryGeocode = (id: number, version: number) =>
  post<JobDetail>(`/jobs/${id}/retry-geocode/`, { version });

export interface MapPin {
  id: number;
  lat: number;
  lng: number;
  status: string;
  technician_id: number | null;
  is_urgent: boolean;
}
export const fetchMapJobs = (filters: JobFilterValues = NO_FILTERS) => {
  const params = filterQuery(filters);
  const qs = params.toString();
  return get<{ results: MapPin[]; truncated: boolean }>(`/map/jobs/${qs ? `?${qs}` : ''}`);
};
