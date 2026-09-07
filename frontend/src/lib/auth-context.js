import { createContext, useContext } from 'react';

/**
 * Authentication state shared by the provider and every consumer.
 *
 * The default is the "no auth configured" shape rather than null, so a
 * component rendered outside the provider degrades to the signed-out view
 * instead of throwing.
 */
export const AuthContext = createContext({
  status: 'disabled',
  loading: false,
  enabled: false,
  signedIn: false,
  user: null,
  signIn: () => {},
  signOut: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}
