import { NavLink } from 'react-router-dom';
import {
  LayoutGrid,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { MODULES, type ModuleKey } from '../../lib/moduleControls';
import { useModuleControls } from './ModuleControlProvider';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  moduleKey?: ModuleKey;
}

const NAV_ITEMS: NavItem[] = [
  ...MODULES.map((module) => ({
    to: module.route,
    label: module.label,
    icon: module.icon,
    moduleKey: module.key,
  })),
  { to: '/dashboard/custom', label: 'Custom Dashboard', icon: <LayoutGrid className="h-5 w-5" /> },
  { to: '/settings', label: 'Settings', icon: <Settings className="h-5 w-5" /> },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { isEnabled } = useModuleControls();
  const visibleItems = NAV_ITEMS.filter((item) => !item.moduleKey || isEnabled(item.moduleKey));

  return (
    <aside
      className={twMerge(
        'flex h-full flex-col border-r border-gray-200 bg-cisco-blue transition-all duration-200 dark:border-gray-700',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Logo area */}
      <div className="flex h-14 items-center justify-between px-4">
        {!collapsed && (
          <span className="text-sm font-bold uppercase tracking-widest text-white">
            NMS Custom
          </span>
        )}
        <button
          onClick={onToggle}
          className="ml-auto text-white/70 hover:text-white"
          aria-label={collapsed ? 'Expand menu' : 'Collapse menu'}
        >
          {collapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-2">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                isActive
                  ? 'bg-white/15 text-white font-medium'
                  : 'text-white/70 hover:bg-white/10 hover:text-white',
              )
            }
            title={collapsed ? item.label : undefined}
          >
            {item.icon}
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
