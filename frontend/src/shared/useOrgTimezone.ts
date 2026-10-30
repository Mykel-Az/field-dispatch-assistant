import { useSyncExternalStore } from 'react';
import { getOrgTimezone, subscribeOrgTimezone } from './jobTime';

/** The organization's zone; re-renders the caller when it changes. */
export const useOrgTimezone = () => useSyncExternalStore(subscribeOrgTimezone, getOrgTimezone);
