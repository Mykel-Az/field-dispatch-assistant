const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export async function checkHealth(): Promise<{ status: string }> {
    const response = await fetch(`${BASE_URL}/health/`);
    if (!response.ok) {
        throw new Error('Failed to check health');
    }
    return response.json();
}

export async function fetchSkills(): Promise<{ skills: string[] }> {
    const response = await fetch(`${BASE_URL}/skills/`);
    if (!response.ok) {
        throw new Error('Failed to fetch skills');
    }
    return response.json();
}