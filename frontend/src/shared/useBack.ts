import { useLocation, useNavigate } from 'react-router-dom';

// "Back" that goes where the person came from (the plan, the map, a filtered
// list), not always to the jobs list. Links that open a job pass
// `state={{ back: 'plan' }}`; the browser history does the rest, so filters,
// the chosen plan day and the map view are all still there on return.

/** Router state for a link that opens a job from the Plan page. */
export const FROM_PLAN = { back: 'plan' } as const;
/** ...from the Map page. */
export const FROM_MAP = { back: 'map' } as const;
/** ...from the Jobs list. */
export const FROM_JOBS = { back: 'jobs' } as const;

const NAMES: Record<string, string> = { plan: 'plan', map: 'map', jobs: 'jobs' };

export function backLabel(state: unknown, hasHistory: boolean): string {
  const key = (state as { back?: unknown } | null)?.back;
  if (typeof key === 'string' && key in NAMES) return `← Back to ${NAMES[key]}`;
  return hasHistory ? '← Back' : '← All jobs';
}

/**
 * Label and action for a back link. With in-app history it steps back; opened
 * directly (a bookmark, a new tab) there is nothing to step back to, so it
 * falls back to the jobs list.
 */
export function useBack(fallback = '/jobs') {
  const location = useLocation();
  const navigate = useNavigate();
  const hasHistory = location.key !== 'default';
  return {
    label: backLabel(location.state, hasHistory),
    go: () => (hasHistory ? navigate(-1) : navigate(fallback)),
  };
}
