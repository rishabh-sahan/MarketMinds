import { createContext, useContext } from 'react';

/** Theme state shared by the provider and every consumer. */
export const ThemeContext = createContext({ theme: 'light', toggleTheme: () => {} });

export function useTheme() {
  return useContext(ThemeContext);
}
