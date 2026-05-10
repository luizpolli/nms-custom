import { Bell, Sun, Moon, Monitor, LogOut, User, Menu } from 'lucide-react';
import { useThemeStore, type Theme } from '../../stores/theme';
import { useAuthStore } from '../../stores/auth';
import { useAlarmWebSocket } from '../../lib/ws';
import { useState } from 'react';
import { clsx } from 'clsx';

interface TopbarProps {
  onMenuToggle: () => void;
}

const THEME_OPTIONS: Array<{ value: Theme; icon: React.ReactNode; label: string }> = [
  { value: 'light', icon: <Sun className="h-4 w-4" />, label: 'Light' },
  { value: 'dark', icon: <Moon className="h-4 w-4" />, label: 'Dark' },
  { value: 'system', icon: <Monitor className="h-4 w-4" />, label: 'System' },
];

export function Topbar({ onMenuToggle }: TopbarProps) {
  const { theme, setTheme } = useThemeStore();
  const { user, logout } = useAuthStore();
  const { connected, lastAlarm } = useAlarmWebSocket();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  // Count unread from WS
  useState(() => {
    if (lastAlarm) setUnread((n) => n + 1);
  });

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 dark:border-gray-700 dark:bg-gray-900">
      {/* Left */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 sm:hidden"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <input
          type="search"
          placeholder="Search devices, alarms..."
          className="hidden w-64 rounded-md border border-gray-300 bg-gray-50 px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-cisco-blue dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 sm:block"
        />
      </div>

      {/* Right */}
      <div className="flex items-center gap-2">
        {/* WS indicator */}
        <span
          title={connected ? 'WebSocket connected' : 'WebSocket disconnected'}
          className={clsx('h-2 w-2 rounded-full', connected ? 'bg-severity-clear' : 'bg-gray-400')}
        />

        {/* Alarm bell */}
        <button
          className="relative p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
          aria-label="Alarms"
          onClick={() => setUnread(0)}
        >
          <Bell className="h-5 w-5" />
          {unread > 0 && (
            <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-severity-critical text-[10px] font-bold text-white">
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </button>

        {/* Theme switcher */}
        <div className="flex items-center rounded-md border border-gray-200 dark:border-gray-700">
          {THEME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              title={opt.label}
              className={clsx(
                'p-1.5 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100',
                theme === opt.value && 'bg-gray-100 text-cisco-blue dark:bg-gray-800 dark:text-cisco-blue-light',
              )}
            >
              {opt.icon}
            </button>
          ))}
        </div>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <User className="h-4 w-4" />
            <span className="hidden sm:inline">{user?.name ?? 'Admin'}</span>
          </button>
          {userMenuOpen && (
            <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-900">
              <button
                onClick={() => { logout(); setUserMenuOpen(false); }}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                <LogOut className="h-4 w-4" />
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
