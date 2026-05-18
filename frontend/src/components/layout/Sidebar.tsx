import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  Package,
  KeyRound,
  Activity,
  RadioTower,
  Bell,
  ShieldCheck,
  Bot,
  SlidersHorizontal,
  ClipboardList,
  Network,
  Radar,
  BookOpen,
  Terminal,
  Layers,
  FileText,
  Settings,
  FlaskConical,
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
  { to: '/devices', label: 'Devices', icon: <Server className="h-5 w-5" /> },
  { to: '/inventory', label: 'Inventory', icon: <Package className="h-5 w-5" /> },
  { to: '/credentials', label: 'Credentials', icon: <KeyRound className="h-5 w-5" /> },
  { to: '/performance', label: 'Performance', icon: <Activity className="h-5 w-5" /> },
  { to: '/telemetry', label: 'Telemetry', icon: <RadioTower className="h-5 w-5" /> },
  { to: '/alarms', label: 'Alarms', icon: <Bell className="h-5 w-5" /> },
  { to: '/assurance', label: 'Assurance', icon: <ShieldCheck className="h-5 w-5" /> },
  { to: '/ai-ops', label: 'AI Ops', icon: <Bot className="h-5 w-5" /> },
  { to: '/lab', label: 'Lab Health', icon: <FlaskConical className="h-5 w-5" /> },
  { to: '/alarm-rules', label: 'Alarm Rules', icon: <SlidersHorizontal className="h-5 w-5" /> },
  { to: '/monitoring-policies', label: 'Monitoring Policies', icon: <ClipboardList className="h-5 w-5" /> },
  { to: '/topology', label: 'Topology', icon: <Network className="h-5 w-5" /> },
  { to: '/discovery', label: 'Discovery', icon: <Radar className="h-5 w-5" /> },
  { to: '/mibs', label: 'MIBs', icon: <BookOpen className="h-5 w-5" /> },
  { to: '/commands', label: 'Commands', icon: <Terminal className="h-5 w-5" /> },
  { to: '/ios', label: 'IOS Versions', icon: <Layers className="h-5 w-5" /> },
  { to: '/reports', label: 'Reports', icon: <FileText className="h-5 w-5" /> },
  { to: '/settings', label: 'Settings', icon: <Settings className="h-5 w-5" /> },
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
          aria-label={collapsed ? 'Expand menu' : 'Collapse menu'}
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
