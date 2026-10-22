// Hand-written API shapes for the auth/users/organization endpoints.
// TIME: these mirror backend/schema.yml by hand. Full-fidelity path: derive
// them from the generated schema.d.ts (`npm run api:types`).

export type Role = 'head_dispatcher' | 'dispatcher' | 'technician';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  organization: { id: number; name: string };
}

export interface SkillRef {
  id: number;
  name: string;
  description?: string | null;
}

/** GET /technicians/ and /technicians/{id}/ (no coordinates, by design). */
export interface Technician {
  id: number;
  user: User;
  skills: SkillRef[];
  shift_start: string; // "HH:MM:SS"
  shift_end: string;
  phone: string | null;
}

export interface TechnicianUpdate {
  skill_ids?: number[];
  shift_start?: string;
  shift_end?: string;
  phone?: string | null;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Organization {
  id: number;
  name: string;
  email: string;
  phone: string;
  address: string;
  lat: number | null;
  lng: number | null;
  geocode_status: 'pending' | 'manual' | 'ok' | 'failed';
  work_start: string | null; // "HH:MM:SS"
  work_end: string | null;
  scoring_strategy: string;
  is_configured: boolean;
  version: number;
}

export interface RegisterInput {
  organization_name: string;
  full_name: string;
  email: string;
  password: string;
}

export interface CreateUserInput {
  email: string;
  password: string;
  full_name: string;
  role: Role;
  technician?: { shift_start: string; shift_end: string; skill_ids?: number[] };
}

export const ROLE_LABEL: Record<Role, string> = {
  head_dispatcher: 'Head dispatcher',
  dispatcher: 'Dispatcher',
  technician: 'Technician',
};