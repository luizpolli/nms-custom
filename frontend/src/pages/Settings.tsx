import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Users,
  ChevronRight,
  Search,
  X,
  Lock,
  FileSearch,
} from 'lucide-react';
import { useAuthStore } from '../stores/auth';
import { Card } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';
import { Input, PageIntroFloat } from '../components/ui';
import { api } from '../lib/api';
import { ForwardingSettings } from './settings/ForwardingSettings';
import { LabHealthPage } from './lab/LabHealthPage';
import {
  CATEGORIES,
  CATEGORY_PERMISSIONS,
  SUBMENU_PERMISSIONS,
  SETTINGS_SECTION_INTRO_STORAGE_PREFIX,
  type Category,
  type CategoryKey,
} from './settings/_shared';
import { ClientsUsersPanel, type AppUser, type AppRole } from './settings/UsersRolesPanel';
import { GeneralPanel, SystemPanel, MailNotificationPanel } from './settings/GeneralSystemPanels';
import { NetworkDevicesPanel, AlarmsEventsPanel, InventorySettingsPanel } from './settings/NetworkAlarmsPanels';
import { ModuleControlSettingsPanel, IntegrationsAiOpsSettingsPanel, LabOperationsSettingsPanel } from './settings/IntegrationsLabPanels';
import { SettingsAuditPanel, AccountAuditPanel } from './settings/AuditPanels';
import { ContainersPanel } from './system/ContainersPanel';
import { BackupsPanel } from './system/BackupsPanel';

// ---------------------------------------------------------------------------
// Tiny wrapper panels that compose two or more sub-panels
// ---------------------------------------------------------------------------

function AccessControlPanel() {
  type AccessControlTab = 'usersRoles' | 'accountAudit';
  const [tab, setTab] = useState<AccessControlTab>('usersRoles');
  const tabs: Array<{ key: AccessControlTab; label: string; icon: React.ReactNode }> = [
    { key: 'usersRoles', label: 'Users & Roles', icon: <Users className="h-4 w-4" /> },
    { key: 'accountAudit', label: 'Account Audit', icon: <FileSearch className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap gap-2 p-3">
          {tabs.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                tab === item.key
                  ? 'border-cisco-blue bg-cisco-blue text-white'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800'
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      </Card>
      {tab === 'usersRoles' ? <ClientsUsersPanel mode="users" /> : <AccountAuditPanel />}
    </div>
  );
}

function NotificationsForwardingPanel() {
  return (
    <div className="space-y-6">
      <MailNotificationPanel />
      <ForwardingSettings />
    </div>
  );
}

// ---------------------------------------------------------------------------
// System Administration panel (containers + backups tabs)
// ---------------------------------------------------------------------------

function SystemAdminPanel() {
  type Tab = 'containers' | 'backups';
  const [tab, setTab] = useState<Tab>('containers');
  const tabs: Array<{ key: Tab; label: string }> = [
    { key: 'containers', label: 'Services & Containers' },
    { key: 'backups',    label: 'Backup Jobs' },
  ];
  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap gap-2 p-3">
          {tabs.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                tab === item.key
                  ? 'border-cisco-blue bg-cisco-blue text-white'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </Card>
      {tab === 'containers' ? <ContainersPanel /> : <BackupsPanel />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Category content router
// ---------------------------------------------------------------------------

function CategoryContent({ category }: { category: CategoryKey }) {
  switch (category) {
    case 'general':
      return <GeneralPanel />;
    case 'system':
      return (
        <div className="space-y-6">
          <SystemPanel />
          <SettingsAuditPanel />
        </div>
      );
    case 'security':
      return <ClientsUsersPanel mode="security" />;
    case 'usersRoles':
      return <AccessControlPanel />;
    case 'networkDevices':
      return (
        <div className="space-y-6">
          <NetworkDevicesPanel />
          <InventorySettingsPanel />
        </div>
      );
    case 'inventory':
      return (
        <div className="space-y-6">
          <NetworkDevicesPanel />
          <InventorySettingsPanel />
        </div>
      );
    case 'alarmsEvents':
      return <AlarmsEventsPanel />;
    case 'eventForwarding':
      return <NotificationsForwardingPanel />;
    case 'modules':
      return <ModuleControlSettingsPanel />;
    case 'integrationsAiOps':
      return <IntegrationsAiOpsSettingsPanel />;
    case 'labOperations':
      return (
        <div className="space-y-6">
          <LabHealthPage embedded />
          <LabOperationsSettingsPanel />
        </div>
      );
    case 'systemAdmin':
      return <SystemAdminPanel />;
  }
}

// ---------------------------------------------------------------------------
// Section intro helpers
// ---------------------------------------------------------------------------

const SECTION_KEYS = new Set<CategoryKey>([
  'general', 'system', 'security', 'usersRoles', 'networkDevices',
  'inventory', 'alarmsEvents', 'eventForwarding', 'modules', 'integrationsAiOps', 'labOperations',
  'systemAdmin',
]);

function isValidSection(s: string | null): s is CategoryKey {
  return s !== null && SECTION_KEYS.has(s as CategoryKey);
}

function normalizeSection(s: string | null): CategoryKey {
  if (s === 'inventory') return 'networkDevices';
  return isValidSection(s) ? s : 'general';
}

function settingsSearchText(category: Category): string {
  return [
    category.title,
    category.description,
    category.status || '',
    ...category.submenus,
  ].join(' ').toLowerCase();
}

function SettingsSectionDiagram({ category, submenus }: { category: Category; submenus: string[] }) {
  const primary = submenus.slice(0, 4);
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-950">
      <div className="grid gap-3 lg:grid-cols-[1fr_auto_1.3fr_auto_1fr] lg:items-center">
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
            <span className="text-cisco-blue">{category.icon}</span>
            <span>{category.title}</span>
          </div>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{category.description}</p>
        </div>
        <div className="hidden text-center text-xl text-gray-400 lg:block">-&gt;</div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Choose a function</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {primary.map((submenu) => (
              <span key={submenu} className="rounded bg-cisco-blue/10 px-2 py-1 text-xs text-cisco-blue dark:bg-cisco-blue/20">
                {submenu}
              </span>
            ))}
            {submenus.length > primary.length && (
              <span className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-500 dark:bg-gray-800">+{submenus.length - primary.length}</span>
            )}
          </div>
        </div>
        <div className="hidden text-center text-xl text-gray-400 lg:block">-&gt;</div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Apply and validate</div>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Update settings, save when available, then validate the related operational page.
          </p>
        </div>
      </div>
    </div>
  );
}

function SettingsSectionIntro({ category, submenus, onDismiss }: { category: Category; submenus: string[]; onDismiss: (options: { dontShowAgain: boolean }) => void }) {
  return (
    <PageIntroFloat title={`${category.title} guide`} icon={category.icon} onDismiss={onDismiss}>
      <p className="mb-3 text-gray-600 dark:text-gray-300">{category.description}</p>
      <SettingsSectionDiagram category={category} submenus={submenus} />
    </PageIntroFloat>
  );
}

// ---------------------------------------------------------------------------
// Main Settings page
// ---------------------------------------------------------------------------

function Settings() {
  const authUser = useAuthStore((state) => state.user);
  const [searchParams, setSearchParams] = useSearchParams();
  const sectionParam = searchParams.get('section');
  const [settingsSearch, setSettingsSearch] = useState('');
  const [navUsers, setNavUsers] = useState<AppUser[]>([]);
  const [navRoles, setNavRoles] = useState<AppRole[]>([]);
  const [active, setActive] = useState<CategoryKey>(
    normalizeSection(sectionParam),
  );
  const [showSectionIntro, setShowSectionIntro] = useState(false);
  const normalizedSearch = settingsSearch.trim().toLowerCase();

  useEffect(() => {
    void Promise.all([
      api.get('/settings/users').then((r) => setNavUsers(r.data)).catch(() => setNavUsers([])),
      api.get('/settings/roles').then((r) => setNavRoles(r.data)).catch(() => setNavRoles([])),
    ]);
  }, []);

  const roleByName = new Map(navRoles.map((role) => [role.name, role]));
  const currentUser = navUsers.find((user) => user.username === authUser?.name);
  const effectivePermissions = (() => {
    const merged: Record<string, boolean> = {};
    const roleNames = currentUser
      ? (currentUser.roles?.length ? currentUser.roles : currentUser.role.split(',')).map((name) => name.trim()).filter(Boolean)
      : authUser?.name === 'admin'
        ? ['admin']
        : [];

    for (const roleName of roleNames) {
      const role = roleByName.get(roleName);
      if (role?.permissions) Object.assign(merged, role.permissions);
    }
    if (currentUser?.custom_permissions) Object.assign(merged, currentUser.custom_permissions);

    // Labs commonly start with a local mock admin but no persisted users/roles yet.
    if (!Object.keys(merged).length && (!authUser || authUser.name === 'admin')) {
      merged['*'] = true;
    }
    return merged;
  })();

  const canAccess = (permissions?: string[]) =>
    !permissions?.length || !!effectivePermissions['*'] || permissions.some((key) => !!effectivePermissions[key]);

  const visibleSubmenus = (cat: Category) => {
    const submenuPermissions = SUBMENU_PERMISSIONS[cat.key] || {};
    return cat.submenus.filter((submenu) => canAccess(submenuPermissions[submenu]));
  };

  const categoryIsAccessible = (cat: Category) =>
    canAccess(CATEGORY_PERMISSIONS[cat.key]) && visibleSubmenus(cat).length > 0;

  const accessibleCategories = CATEGORIES.filter(categoryIsAccessible);
  const visibleCategories = (normalizedSearch
    ? accessibleCategories.filter((cat) => settingsSearchText({ ...cat, submenus: visibleSubmenus(cat) }).includes(normalizedSearch))
    : accessibleCategories);

  const handleSelect = (key: CategoryKey) => {
    if (!accessibleCategories.some((cat) => cat.key === key)) return;
    setActive(key);
    setSearchParams({ section: key }, { replace: true });
  };

  const activeCategory = CATEGORIES.find((cat) => cat.key === active) ?? CATEGORIES[0];
  const activeSubmenus = visibleSubmenus(activeCategory);
  const dismissSectionIntro = ({ dontShowAgain }: { dontShowAgain: boolean }) => {
    if (dontShowAgain) window.localStorage.setItem(`${SETTINGS_SECTION_INTRO_STORAGE_PREFIX}-${active}`, 'true');
    setShowSectionIntro(false);
  };

  // Sync if URL param changes externally (e.g. back/forward navigation).
  useEffect(() => {
    const s = searchParams.get('section');
    const normalized = normalizeSection(s);
    if (normalized !== active) setActive(normalized);
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!accessibleCategories.some((cat) => cat.key === active) && accessibleCategories.length) {
      handleSelect(accessibleCategories[0].key);
    }
  }, [active, accessibleCategories.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (typeof window === 'undefined') return;
    setShowSectionIntro(window.localStorage.getItem(`${SETTINGS_SECTION_INTRO_STORAGE_PREFIX}-${active}`) !== 'true');
  }, [active]);

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="System Settings"
        subtitle="The product allows an administrator to configure or modify the network and system wide settings."
      />

      <div className="grid grid-cols-12 gap-6">
        {showSectionIntro && activeCategory && (
          <SettingsSectionIntro category={activeCategory} submenus={activeSubmenus} onDismiss={dismissSectionIntro} />
        )}
        <aside className="col-span-12 md:col-span-4 lg:col-span-3 space-y-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <Input
              type="search"
              value={settingsSearch}
              onChange={(e) => setSettingsSearch(e.target.value)}
              placeholder="Search settings..."
              className="pl-9 pr-9"
              aria-label="Search settings"
            />
            {settingsSearch && (
              <button
                type="button"
                onClick={() => setSettingsSearch('')}
                className="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200"
                aria-label="Clear settings search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {visibleCategories.map((cat) => {
            const allowedSubmenus = visibleSubmenus(cat);
            const matchedSubmenus = normalizedSearch
              ? allowedSubmenus.filter((submenu) => submenu.toLowerCase().includes(normalizedSearch))
              : allowedSubmenus.slice(0, 3);

            return (
              <button
                key={cat.key}
                onClick={() => handleSelect(cat.key)}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  active === cat.key
                    ? 'border-cisco-blue bg-cisco-blue/5 ring-1 ring-cisco-blue'
                    : 'border-gray-200 bg-white hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cisco-blue text-xs font-bold text-white">
                    {cat.number}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-cisco-blue dark:text-cisco-blue-light">{cat.icon}</span>
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{cat.title}</h3>
                      {cat.status && (
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                          cat.status === 'live'
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                            : cat.status === 'partial'
                              ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                              : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
                        }`}>
                          {cat.status}
                        </span>
                      )}
                      {allowedSubmenus.length < cat.submenus.length && (
                        <span title="Some submenus are hidden by permissions" className="text-gray-400">
                          <Lock className="h-3.5 w-3.5" />
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs leading-snug text-gray-600 dark:text-gray-400 line-clamp-3">
                      {cat.description}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(matchedSubmenus.length ? matchedSubmenus : allowedSubmenus.slice(0, 3)).slice(0, 3).map((submenu) => (
                        <span key={submenu} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                          {submenu}
                        </span>
                      ))}
                      {!normalizedSearch && allowedSubmenus.length > 3 && (
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-800">
                          +{allowedSubmenus.length - 3}
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                </div>
              </button>
            );
          })}

          {visibleCategories.length === 0 && (
            <div className="rounded-lg border border-dashed border-gray-300 bg-white p-4 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
              No matching settings sections.
            </div>
          )}
        </aside>

        <main className="col-span-12 md:col-span-8 lg:col-span-9">
          <CategoryContent category={active} />
        </main>
      </div>
    </div>
  );
}

export default Settings;
