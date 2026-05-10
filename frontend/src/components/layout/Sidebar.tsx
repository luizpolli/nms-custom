import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  Package,
  KeyRound,
  Activity,
  Bell,
  Network,
  Radar,
  BookOpen,
  Terminal,
  Layers,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: <LayoutDashboard className="h-5 w-5" /> },
  { to: '/devices', label: 'Dispositivos', icon: <Server className="h-5 w-5" /> },
  { to: '/inventory', label: 'Inventario', icon: <Package className="h-5 w-5" /> },
  { to: '/credentials', label: 'Credenciales', icon: <KeyRound className="h-5 w-5" /> },
  { to: '/performance', label: 'Rendimiento', icon: <Activity className="h-5 w-5" /> },
  { to: '/alarms', label: 'Alarmas', icon: <Bell className="h-5 w-5" /> },
  { to: '/topology', label: 'Topología', icon: <Network className="h-5 w-5" /> },
  { to: '/discovery', label: 'Descubrimiento', icon: <Radar className="h-5 w-5" /> },
  { to: '/mibs', label: 'MIBs', icon: <BookOpen className="h-5 w-5" /> },
  { to: '/commands', label: 'Comandos', icon: <Terminal className="h-5 w-5" /> },
  { to: '/ios', label: 'Versiones IOS', icon: <Layers className="h-5 w-5" /> },
  { to: '/reports', label: 'Reportes', icon: <FileText className="h-5 w-5" /> },
  { to: '/settings', label: 'Configuración', icon: <Settings className="h-5 w-5" /> },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
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
          aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          {collapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV_ITEMS.map((item) => (
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
