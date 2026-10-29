import type { components } from './schema';

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

// --- jobs: derived from the generated schema (`npm run api:types`) ---
export type JobRow = components['schemas']['Job'];
export type JobDetail = components['schemas']['JobDetail'];
export type JobHistoryRow = components['schemas']['JobHistory'];
export type JobCreateInput = components['schemas']['JobCreate'];
export type JobUpdateInput = components['schemas']['PatchedJobUpdate'] & { version: number };
export type JobCategory = components['schemas']['CategoryEnum'];
export type GeocodeStatus = components['schemas']['GeocodeStatusEnum'];

export const CATEGORY_LABEL: Record<JobCategory, string> = {
  hvac: 'HVAC',
  electrical: 'Electrical',
  appliance: 'Appliance repair',
};

// TIME: category -> default skill NAME, mirroring the CandidateSkillRule seed.
// Full-fidelity path: the API returns each category's default skill ids, so the
// form can never drift from the table.
export const CATEGORY_DEFAULT_SKILL: Record<JobCategory, string> = {
  hvac: 'HVAC',
  electrical: 'Electrical',
  appliance: 'Appliance Repair',
};

// TIME: starting estimate per category until the algorithm learns real durations.
export const CATEGORY_DEFAULT_MINUTES: Record<JobCategory, number> = {
  hvac: 120,
  electrical: 90,
  appliance: 60,
};
