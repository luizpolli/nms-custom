/**
 * Tests for the axios instance in src/lib/api.ts.
 *
 * The two behaviours we lock in:
 *
 *  1. The request interceptor reads `nms_api_key` from localStorage and
 *     attaches it to every outgoing request as `X-API-Key`. If the user
 *     hasn't authenticated yet, the header must NOT be set.
 *
 *  2. The response interceptor dispatches a global `api-error` CustomEvent
 *     whenever a request fails. The dispatched detail is the resolved error
 *     message in this priority: `response.data.detail` > `response.data.message`
 *     > `error.message` > "Unknown error". The Toast component listens to that
 *     event, so this contract is load-bearing.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import axios from 'axios';
import { api } from './api';

const getRequestInterceptor = () => {
  // Axios stores handlers in `interceptors.request.handlers`; the latest one
  // added is what api.ts registered.
  const handlers = (api.interceptors.request as unknown as { handlers: Array<{ fulfilled: (c: InternalAxiosRequestConfig) => InternalAxiosRequestConfig }> }).handlers;
  return handlers[handlers.length - 1].fulfilled;
};

const getResponseInterceptorReject = () => {
  const handlers = (api.interceptors.response as unknown as { handlers: Array<{ rejected: (e: AxiosError) => unknown }> }).handlers;
  return handlers[handlers.length - 1].rejected;
};

const makeConfig = (): InternalAxiosRequestConfig => {
  // Axios 1.x uses an AxiosHeaders instance; create a fresh one per call so
  // tests don't pollute each other.
  const headers = new axios.AxiosHeaders();
  return { headers } as InternalAxiosRequestConfig;
};

describe('api request interceptor', () => {
  it('does not attach X-API-Key when localStorage has no key', () => {
    const cfg = makeConfig();
    const out = getRequestInterceptor()(cfg);
    expect(out.headers.get('X-API-Key')).toBeUndefined();
  });

  it('attaches the stored API key as X-API-Key', () => {
    window.localStorage.setItem('nms_api_key', 'super-secret-key');
    const cfg = makeConfig();
    const out = getRequestInterceptor()(cfg);
    expect(out.headers.get('X-API-Key')).toBe('super-secret-key');
  });
});

describe('api response interceptor', () => {
  let dispatched: string[] = [];
  const listener = (e: Event) => {
    dispatched.push((e as CustomEvent<string>).detail);
  };

  beforeEach(() => {
    dispatched = [];
    window.addEventListener('api-error', listener);
  });

  afterEach(() => {
    window.removeEventListener('api-error', listener);
  });

  it('prefers response.data.detail over message', async () => {
    const err = {
      response: { data: { detail: 'Boom from server', message: 'fallback' } },
      message: 'axios fallback',
    } as unknown as AxiosError;
    await expect(getResponseInterceptorReject()(err)).rejects.toBe(err);
    expect(dispatched).toEqual(['Boom from server']);
  });

  it('falls through to response.data.message when detail is missing', async () => {
    const err = {
      response: { data: { message: 'Server explained the failure' } },
      message: 'axios fallback',
    } as unknown as AxiosError;
    await expect(getResponseInterceptorReject()(err)).rejects.toBe(err);
    expect(dispatched).toEqual(['Server explained the failure']);
  });

  it('falls through to error.message when the server says nothing useful', async () => {
    const err = { message: 'Network Error' } as unknown as AxiosError;
    await expect(getResponseInterceptorReject()(err)).rejects.toBe(err);
    expect(dispatched).toEqual(['Network Error']);
  });

  it('falls back to "Unknown error" when everything is empty', async () => {
    const err = {} as unknown as AxiosError;
    await expect(getResponseInterceptorReject()(err)).rejects.toBe(err);
    expect(dispatched).toEqual(['Unknown error']);
  });

  it('re-rejects the original error so callers see it', async () => {
    const err = { message: 'kaboom' } as unknown as AxiosError;
    const reject = vi.fn();
    const result = getResponseInterceptorReject()(err) as Promise<unknown>;
    await result.catch(reject);
    expect(reject).toHaveBeenCalledWith(err);
  });
});
