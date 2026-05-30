/**
 * Shared test helpers and wrapper utilities.
 *
 * Provides:
 * - renderWithProviders: wraps components in QueryClientProvider + MemoryRouter
 * - makeQueryClient: fresh QueryClient with retries disabled for fast tests
 * - mockApiGet / mockApiPost: simple vi.mock helpers for api.ts
 */
import { type ReactNode } from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom';

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

interface WrapperOptions extends RenderOptions {
  routerProps?: MemoryRouterProps;
  queryClient?: QueryClient;
}

export function renderWithProviders(
  ui: ReactNode,
  { routerProps, queryClient, ...renderOptions }: WrapperOptions = {},
) {
  const client = queryClient ?? makeQueryClient();
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter {...routerProps}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  return { ...render(ui, { wrapper: Wrapper, ...renderOptions }), queryClient: client };
}
