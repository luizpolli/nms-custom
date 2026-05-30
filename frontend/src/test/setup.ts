/**
 * Global test setup loaded by vitest.config.ts.
 *
 * - Adds @testing-library/jest-dom matchers (toBeInTheDocument, etc.).
 * - Provides an in-memory localStorage shim. happy-dom's storage doesn't
 *   always survive Node 26's experimental built-in `localStorage`, which
 *   ships in the runtime but is unusable without a file backing. The shim
 *   below is what the api.ts interceptor actually reads.
 * - Wipes storage between tests so interceptor state doesn't leak.
 * - Stubs `window.confirm` (and `alert`/`prompt`) which happy-dom 20 no
 *   longer exposes by default. Tests that exercise delete flows spy on
 *   `window.confirm`, which fails with "can only spy on a function" unless
 *   we install a no-op stub first.
 */

import '@testing-library/jest-dom/vitest';
import { afterEach, beforeAll } from 'vitest';
import { cleanup } from '@testing-library/react';

class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length() {
    return this.store.size;
  }
  clear() {
    this.store.clear();
  }
  getItem(key: string) {
    return this.store.has(key) ? (this.store.get(key) as string) : null;
  }
  key(index: number) {
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string) {
    this.store.delete(key);
  }
  setItem(key: string, value: string) {
    this.store.set(key, String(value));
  }
}

beforeAll(() => {
  const storage = new MemoryStorage();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: storage,
  });
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: storage,
  });

  // happy-dom 20 no longer ships window.confirm/alert/prompt. Install
  // permissive no-op stubs so vi.spyOn(window, 'confirm') works.
  for (const name of ['confirm', 'alert', 'prompt'] as const) {
    if (typeof (window as unknown as Record<string, unknown>)[name] !== 'function') {
      Object.defineProperty(window, name, {
        configurable: true,
        writable: true,
        value: name === 'confirm' ? () => true : () => undefined,
      });
    }
  }
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});
