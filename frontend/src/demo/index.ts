import type { InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { matchDemoHandler } from './handlers';

const STORAGE_KEY = 'nms_demo_mode';

export function isDemoEnabled(): boolean {
  return window.localStorage.getItem(STORAGE_KEY) === 'true';
}

export function setDemoMode(enabled: boolean): void {
  if (enabled) {
    window.localStorage.setItem(STORAGE_KEY, 'true');
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
  // Trigger a full page reload so React Query re-fetches everything with the
  // new adapter state — simplest way to flush the query cache cleanly.
  window.location.reload();
}

export function installDemoInterceptor(
  axiosInstance: { interceptors: { request: { use: (fn: (cfg: InternalAxiosRequestConfig) => InternalAxiosRequestConfig) => void } } }
): void {
  axiosInstance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    if (!isDemoEnabled()) return config;

    const params = config.params as Record<string, string> | undefined;
    const mockData = matchDemoHandler(config.url, config.method, params);

    if (mockData !== undefined) {
      // Swap in a custom adapter that short-circuits the real HTTP request
      config.adapter = (): Promise<AxiosResponse> =>
        Promise.resolve({
          data: mockData,
          status: 200,
          statusText: 'OK (demo)',
          headers: {},
          config,
        } as AxiosResponse);
    } else {
      // Block write operations in demo mode — return success without hitting backend
      const method = (config.method ?? 'get').toLowerCase();
      if (['post', 'put', 'patch', 'delete'].includes(method)) {
        config.adapter = (): Promise<AxiosResponse> =>
          Promise.resolve({
            data: { ok: true, demo: true },
            status: 200,
            statusText: 'OK (demo)',
            headers: {},
            config,
          } as AxiosResponse);
      }
    }

    return config;
  });
}
