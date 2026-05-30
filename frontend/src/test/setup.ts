/**
 * Global test setup loaded by vitest.config.ts.
 *
 * - Adds @testing-library/jest-dom matchers (toBeInTheDocument, etc.).
 * - Provides an in-memory localStorage shim. happy-dom's storage doesn't
 *   always survive Node 26's experimental built-in `localStorage`, which
 *   ships in the runtime but is unusable without a file backing. The shim
 *   below is what the api.ts interceptor actually reads.
 * - Wipes storage between tests so interceptor state doesn't leak.
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
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});
