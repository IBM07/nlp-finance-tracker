import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiClient, { setTokens, clearTokens, registerRefreshCallback } from '../api/client';

// ─────────────────────────────────────────────────────────
//  AuthContext — holds JWT in React state (in-memory only).
//  Never writes to localStorage. XSS-resistant.
// ─────────────────────────────────────────────────────────

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);       // { id, email, created_at }
  const [accessToken, setAccessToken] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Register callback so client.js can update context after silent refresh
  useEffect(() => {
    registerRefreshCallback((data) => {
      setAccessToken(data.access_token);
    });
  }, []);

  const login = useCallback(async (email, password) => {
    setIsLoading(true);
    try {
      const { data } = await apiClient.post('/auth/login', { email, password });
      setTokens(data.access_token, data.refresh_token);
      setAccessToken(data.access_token);

      // Fetch user profile
      const { data: userData } = await apiClient.get('/auth/me');
      setUser(userData);
      return { success: true };
    } catch (err) {
      const message = err.response?.data?.detail || 'Login failed. Please check your credentials.';
      return { success: false, message };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const signup = useCallback(async (email, password) => {
    setIsLoading(true);
    try {
      await apiClient.post('/auth/signup', { email, password });
      // Auto-login after signup
      return await login(email, password);
    } catch (err) {
      const message = err.response?.data?.detail || 'Signup failed. Please try again.';
      return { success: false, message };
    } finally {
      setIsLoading(false);
    }
  }, [login]);

  const logout = useCallback(() => {
    // Clear in-memory tokens; page reload completes the logout
    clearTokens();
    setAccessToken(null);
    setUser(null);
  }, []);

  const isAuthenticated = Boolean(accessToken && user);

  return (
    <AuthContext.Provider value={{ user, accessToken, isAuthenticated, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
