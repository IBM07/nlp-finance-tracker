import { createContext, useContext, useState, useCallback } from 'react';

// ─────────────────────────────────────────────────────────
//  DataRefreshContext — a single incrementing counter that pages
//  watch (via useEffect deps) to know when to refetch. Needed
//  because AppShell now persists across route changes, so a chat
//  mutation on one page must be able to tell whichever page is
//  currently mounted to reload its data.
// ─────────────────────────────────────────────────────────

const DataRefreshContext = createContext(null);

export function DataRefreshProvider({ children }) {
  const [refreshToken, setRefreshToken] = useState(0);
  const bumpRefresh = useCallback(() => setRefreshToken((n) => n + 1), []);

  return (
    <DataRefreshContext.Provider value={{ refreshToken, bumpRefresh }}>
      {children}
    </DataRefreshContext.Provider>
  );
}

export function useDataRefresh() {
  const ctx = useContext(DataRefreshContext);
  if (!ctx) throw new Error('useDataRefresh must be used within <DataRefreshProvider>');
  return ctx;
}
