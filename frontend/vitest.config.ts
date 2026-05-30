/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Vitest config is kept separate from vite.config.ts so the dev/build
// pipeline never accidentally pulls in jsdom, @testing-library, or any
// of the other test-only deps.
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    // happy-dom is materially faster than jsdom and — critically — plays
    // well with Node 26's experimental built-in localStorage, which jsdom
    // 25 fights with on this runtime.
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.{test,spec}.{ts,tsx}',
        'src/test/**',
        'src/main.tsx',
        'src/router.tsx',
      ],
    },
  },
});
