// Reads the backend URL from Vite environment variables.
// Set VITE_API_URL in .env for local dev, and in Cloudflare Pages env for production.
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
