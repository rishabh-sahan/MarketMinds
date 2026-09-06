import { useCallback, useEffect, useState } from 'react';
import { ThemeContext } from '../lib/theme-context';

const STORAGE_KEY = 'mm-theme';

function readStored() {
  // Light is the default; a stored value only ever overrides it. Storage can
  // throw outright in private mode, so every access is guarded.
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === 'dark' || stored === 'light' ? stored : 'light';
  } catch {
    return 'light';
  }
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(readStored);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', theme === 'dark' ? '#131316' : '#faf9f7');
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* not persisting is fine — the session still renders correctly */
    }
  }, [theme]);

  const toggleTheme = useCallback(
    () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
    [],
  );

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>
  );
}
