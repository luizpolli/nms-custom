import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'light' | 'dark' | 'system';

interface ThemeStore {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

function applyTheme(theme: Theme): void {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = theme === 'dark' || (theme === 'system' && prefersDark);
  document.documentElement.classList.toggle('dark', isDark);
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: 'system',
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
    }),
    { name: 'nms-theme' },
  ),
);

export function initTheme(): void {
  const stored = localStorage.getItem('nms-theme');
  let theme: Theme = 'system';
  if (stored) {
    try {
      const parsed = JSON.parse(stored) as { state?: { theme?: Theme } };
      theme = parsed.state?.theme ?? 'system';
    } catch {
      // use default
    }
  }
  applyTheme(theme);
}
