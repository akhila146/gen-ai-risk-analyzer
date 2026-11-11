import axios from 'axios';
import { clearAuthentication, getAccessToken } from './auth';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use(async (config) => {
  const base = new URL(API_BASE_URL, window.location.origin);
  const target = new URL(config.url, base);
  if (target.origin !== base.origin) throw new Error('Refusing to send credentials to another origin.');
  const token = await getAccessToken();
  config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) await clearAuthentication();
    return Promise.reject(error);
  },
);
