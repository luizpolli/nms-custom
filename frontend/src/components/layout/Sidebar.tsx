import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutGrid,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Server,
} from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { MODULES, moduleByKey, type ModuleKey, type ModuleMeta } from '../../lib/moduleControls';
import { useModuleControls } from './ModuleControlProvider';

interface NavItem {
  to?: string;
  label: string;
  icon: React.ReactNode;
  moduleKey?: ModuleKey;
  children?: NavItem[];
}

const moduleNav = (module: ModuleMeta): NavItem => ({
  to: module.route,
  label: module.label,
  icon: module.icon,
  moduleKey: module.key,
});

// Aggregate the standalone "Devices" and "Inventory" modules under a single
// "Devices" parent menu: Devices > Inventory (managed device list) and
// Devices > Chassis (hardware inventory).
const DEVICES_GROUP: NavItem = {
  label: 'Devices',
  icon: <Server className="h-5 w-5" />,
  children: [
    { to: '/devices', label: 'Inventory', icon: moduleByKey.devices.icon, moduleKey: 'devices' },
    { to: '/inventory', label: 'Chassis', icon: moduleByKey.inventory.icon, moduleKey: 'inventory' },
  ],
};

const NAV_ITEMS: NavItem[] = [
  ...MODULES.flatMap((module) => {
    if (module.key === 'devices') return [DEVICES_GROUP];
    if (module.key === 'inventory') return [];
    return [moduleNav(module)];
  }),
  { to: '/dashboard/custom', label: 'Custom Dashboard', icon: <LayoutGrid className="h-5 w-5" /> },
  { to: '/settings', label: 'Settings', icon: <Settings className="h-5 w-5" /> },
];

const linkClass = (isActive: boolean) =>
  clsx(
    'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
    isActive
      ? 'bg-white/15 text-white font-medium'
      : 'text-white/70 hover:bg-white/10 hover:text-white',
  );

interface NavLeafProps {
  item: NavItem;
  collapsed: boolean;
  indent?: boolean;
}

function NavLeaf({ item, collapsed, indent }: NavLeafProps) {
  return (
    <NavLink
      to={item.to!}
      end={item.to === '/'}
      className={({ isActive }) => clsx(linkClass(isActive), indent && !collapsed && 'pl-11')}
      title={collapsed ? item.label : undefined}
    >
      {item.icon}
      {!collapsed && <span>{item.label}</span>}
    </NavLink>
  );
}

interface NavGroupProps {
  item: NavItem;
  collapsed: boolean;
  isEnabled: (key: ModuleKey) => boolean;
  open: boolean;
  onToggle: () => void;
}

function NavGroup({ item, collapsed, isEnabled, open, onToggle }: NavGroupProps) {
  const children = (item.children ?? []).filter(
    (child) => !child.moduleKey || isEnabled(child.moduleKey),
  );

  // When collapsed there is no room for the parent header, so surface the
  // child links directly as icons.
  if (collapsed) {
    return (
      <>
        {children.map((child) => (
          <NavLeaf key={child.to} item={child} collapsed />
        ))}
      </>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-white/70 transition-colors hover:bg-white/10 hover:text-white"
        aria-expanded={open}
      >
        {item.icon}
        <span className="flex-1 text-left">{item.label}</span>
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </button>
      {open &&
        children.map((child) => <NavLeaf key={child.to} item={child} collapsed={false} indent />)}
    </div>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { isEnabled } = useModuleControls();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ Devices: true });

  const isItemVisible = (item: NavItem): boolean => {
    if (item.children) return item.children.some(isItemVisible);
    return !item.moduleKey || isEnabled(item.moduleKey);
  };
  const visibleItems = NAV_ITEMS.filter(isItemVisible);

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
        {visibleItems.map((item) =>
          item.children ? (
            <NavGroup
              key={item.label}
              item={item}
              collapsed={collapsed}
              isEnabled={isEnabled}
              open={expanded[item.label] ?? true}
              onToggle={() =>
                setExpanded((state) => ({ ...state, [item.label]: !(state[item.label] ?? true) }))
              }
            />
          ) : (
            <NavLeaf key={item.to} item={item} collapsed={collapsed} />
          ),
        )}
      </nav>
    </aside>
  );
}
