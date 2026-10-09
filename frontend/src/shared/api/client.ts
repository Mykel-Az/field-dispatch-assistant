import type { components } from './schema';

export type Skill = components['schemas']['Skill'];
export type Health = components['schemas']['Health'];

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

async function get<T>(path: string): Promise<T> {
    const response = await fetch(`${BASE_URL}${path}`);
    if (!response.ok) {
        throw new Error(`GET ${path} failed: ${response.status}`);
    }
    return response.json() as Promise<T>;
}

export const checkHealth = () => get<Health>('/health/');
export const fetchSkills = () => get<Skill[]>('/skills/');