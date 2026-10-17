import { createContext } from 'react';
import type { User } from '../shared/api/models';

export interface AuthState {
  /** undefined while the first /auth/me/ call is in flight. */
  user: User | null | undefined;
  signIn: (email: string, password: string) => Promise<User>;
  signUp: (input: {
    organization_name: string;
    full_name: string;
    email: string;
    password: string;
  }) => Promise<User>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);