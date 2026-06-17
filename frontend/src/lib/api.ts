import axios, { AxiosError } from 'axios';
import { installDemoInterceptor } from '../demo/index';

export const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

// Must run before auth interceptor so demo adapter is installed first
installDemoInterceptor(api);

api.interceptors.request.use((config) => {
  const apiKey = window.localStorage.getItem('nms_api_key');
  if (apiKey) {
    config.headers.set('X-API-Key', apiKey);
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    const message =
      error.response?.data?.detail ??
      error.response?.data?.message ??
      error.message ??
      'Unknown error';

    // Dispatch a custom event so Toast can pick it up without coupling
    window.dispatchEvent(new CustomEvent('api-error', { detail: message }));

    return Promise.reject(error);
  },
);
