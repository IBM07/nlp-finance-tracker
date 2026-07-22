import { createContext, useContext, useEffect, useState, useCallback } from 'react';

// ─────────────────────────────────────────────────────────
//  ThemeContext — light/dark mode. Persisted to localStorage
//  under a UI-preference key, distinct from auth tokens (which
//  are deliberately kept in-memory only — see AuthContext).
// ─────────────────────────────────────────────────────────

const ThemeContext = createContext(null);
const STORAGE_KEY = 'fintrack-theme';

function getStoredTheme() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : null;
}

export function ThemeProvider({ children }) {
  // Light is the default when the user hasn't made an explicit choice;
  // the OS's prefers-color-scheme is intentionally ignored so the site
  // always opens in light mode until the user toggles to dark.
  const [theme, setTheme] = useState(() => getStoredTheme() || 'light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const resolvedTheme = theme;

  return (
    <ThemeContext.Provider value={{ theme: resolvedTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within <ThemeProvider>');
  return ctx;
}
