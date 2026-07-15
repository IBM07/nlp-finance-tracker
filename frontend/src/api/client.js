import axios from 'axios';
import { API_URL } from '../config';

// ─────────────────────────────────────────────────────────
//  Axios instance — all requests go through this client.
//  JWT is stored in memory (AuthContext), not localStorage.
//  The interceptor below reads from module-level storage.
// ─────────────────────────────────────────────────────────

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Module-level token storage (in-memory, not localStorage — XSS-safe)
let _accessToken = null;
let _refreshToken = null;
let _onTokenRefreshed = null; // callback to update AuthContext after refresh

export function setTokens(access, refresh) {
  _accessToken = access;
  _refreshToken = refresh;
}

export function clearTokens() {
  _accessToken = null;
  _refreshToken = null;
}

export function registerRefreshCallback(cb) {
  _onTokenRefreshed = cb;
}

// ── Request interceptor: attach JWT ──────────────────────
apiClient.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers['Authorization'] = `Bearer ${_accessToken}`;
  }
  return config;
});

// ── Response interceptor: auto-refresh on 401 ────────────
let _isRefreshing = false;
let _failedQueue = [];

function processQueue(error, token = null) {
  _failedQueue.forEach(({ resolve, reject }) =>
    error ? reject(error) : resolve(token)
  );
  _failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry && _refreshToken) {
      if (_isRefreshing) {
        return new Promise((resolve, reject) => {
          _failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers['Authorization'] = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      _isRefreshing = true;

      try {
        const { data } = await axios.post(`${API_URL}/auth/refresh`, {
          refresh_token: _refreshToken,
        });
        setTokens(data.access_token, data.refresh_token);
        if (_onTokenRefreshed) _onTokenRefreshed(data);
        processQueue(null, data.access_token);
        originalRequest.headers['Authorization'] = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        _isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
