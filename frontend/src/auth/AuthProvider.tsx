import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { fetchMe, login, logout, register } from '../shared/api/client';
import { setUnauthorizedHandler } from '../shared/api/http';
import type { User } from '../shared/api/models';
import { AuthContext, type AuthState } from './AuthContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);


  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const u = await login(email, password);
    setUser(u);
    return u;
  }, []);

  const signUp = useCallback<AuthState['signUp']>(async (input) => {
    const u = await register(input);
    setUser(u);
    return u;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, signIn, signUp, signOut }),
    [user, signIn, signUp, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}