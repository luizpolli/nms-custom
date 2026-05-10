import axios, { AxiosError } from 'axios';

export const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    const message =
      error.response?.data?.detail ??
      error.response?.data?.message ??
      error.message ??
      'Error desconocido';

    // Dispatch a custom event so Toast can pick it up without coupling
    window.dispatchEvent(new CustomEvent('api-error', { detail: message }));

    return Promise.reject(error);
  },
);
