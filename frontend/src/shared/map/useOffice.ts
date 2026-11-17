import { useEffect, useState } from 'react';
import { fetchOrganization } from '../api/client';
import type { LatLng } from './PinMap';

/**
 * Where the office is, for the maps. `null` until known, and stays null when the
 * organization has no location yet or the call fails: a map without the office
 * marker is still useful.
 */
export function useOffice(): LatLng | null {
  const [office, setOffice] = useState<LatLng | null>(null);
  useEffect(() => {
    let live = true;
    fetchOrganization()
      .then((org) => {
        if (live && org.lat !== null && org.lng !== null) setOffice({ lat: org.lat, lng: org.lng });
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return office;
}
