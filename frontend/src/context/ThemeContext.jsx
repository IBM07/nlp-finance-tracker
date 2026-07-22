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

function systemPrefersDark() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export function ThemeProvider({ children }) {
  // null = no explicit user choice yet; CSS falls back to prefers-color-scheme
  const [explicitTheme, setExplicitTheme] = useState(getStoredTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (explicitTheme) {
      root.setAttribute('data-theme', explicitTheme);
    } else {
      root.removeAttribute('data-theme');
    }
  }, [explicitTheme]);

  const toggleTheme = useCallback(() => {
    setExplicitTheme((prev) => {
      const current = prev || (systemPrefersDark() ? 'dark' : 'light');
      const next = current === 'dark' ? 'light' : 'dark';
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const resolvedTheme = explicitTheme || (systemPrefersDark() ? 'dark' : 'light');

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
