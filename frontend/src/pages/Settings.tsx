import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import {
  Settings as SettingsIcon,
  Network,
  Package,
  Bell,
  Users,
  ShieldCheck,
  ServerCog,
  BrainCircuit,
  FlaskConical,
  ChevronRight,
  Info,
  CheckCircle2,
  XCircle,
  Search,
  X,
} from 'lucide-react';
import { useThemeStore, type Theme } from '../stores/theme';
import { Card, CardHeader } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';
import { Select } from '../components/ui/Select';
import { Button, Input, Badge } from '../components/ui';
import { api } from '../lib/api';

type CategoryKey =
  | 'general'
  | 'system'
  | 'security'
  | 'usersRoles'
  | 'networkDevices'
  | 'inventory'
  | 'alarmsEvents'
  | 'integrationsAiOps'
  | 'labOperations';

interface Category {
  key: CategoryKey;
  number: number;
  title: string;
  description: string;
  icon: React.ReactNode;
  submenus: string[];
  status?: 'live' | 'partial' | 'planned';
}

const CATEGORIES: Category[] = [
  {
    key: 'general',
    number: 1,
    title: 'General',
    description: 'Global UI preferences, product identity, support metadata, and TAC/cisco.com placeholders.',
    icon: <SettingsIcon className="h-5 w-5" />,
    submenus: ['Appearance', 'Polling summary', 'cisco.com / TAC'],
    status: 'partial',
  },
  {
    key: 'system',
    number: 2,
    title: 'System',
    description: 'Server, database, jobs, mail, backups, software updates, and runtime tuning.',
    icon: <ServerCog className="h-5 w-5" />,
    submenus: ['Server tuning', 'Database', 'Jobs', 'Mail notifications', 'Backups', 'Software updates'],
    status: 'planned',
  },
  {
    key: 'security',
    number: 3,
    title: 'Security',
    description: 'HTTPS/TLS, API authentication, root login, session limits, and certificate settings.',
    icon: <ShieldCheck className="h-5 w-5" />,
    submenus: ['HTTPS / TLS', 'Certificates', 'API auth', 'Sessions'],
    status: 'live',
  },
  {
    key: 'usersRoles',
    number: 4,
    title: 'Users / Roles',
    description: 'Local Web GUI and NBI users, Cisco-style built-in roles, custom roles, and task permissions.',
    icon: <Users className="h-5 w-5" />,
    submenus: ['Users', 'Roles', 'Task permissions', 'Virtual domains'],
    status: 'live',
  },
  {
    key: 'networkDevices',
    number: 5,
    title: 'Network Devices',
    description: 'Device access defaults, CLI/SNMP behavior, Plug & Play onboarding, and controller upgrades.',
    icon: <Network className="h-5 w-5" />,
    submenus: ['CLI session', 'SNMP defaults', 'Credentials policy', 'Plug & Play', 'Controller upgrades'],
    status: 'planned',
  },
  {
    key: 'inventory',
    number: 6,
    title: 'Inventory',
    description: 'Configuration archives, image management, discovery defaults, groups, and lifecycle settings.',
    icon: <Package className="h-5 w-5" />,
    submenus: ['Config archives', 'Image management', 'Discovery', 'Device groups', 'Lifecycle'],
    status: 'planned',
  },
  {
    key: 'alarmsEvents',
    number: 7,
    title: 'Alarms / Events',
    description: 'Severity mappings, trap/syslog intake, event retention, notification rules, and suppression defaults.',
    icon: <Bell className="h-5 w-5" />,
    submenus: ['Severity mapping', 'Trap storage', 'Syslog', 'Event retention', 'Notifications'],
    status: 'planned',
  },
  {
    key: 'integrationsAiOps',
    number: 8,
    title: 'Integrations / AI Ops',
    description: 'Northbound APIs, webhooks, AI Ops recommendations, model/provider knobs, and external tools.',
    icon: <BrainCircuit className="h-5 w-5" />,
    submenus: ['Northbound API', 'Webhooks', 'AI Ops', 'LLM providers', 'Export targets'],
    status: 'planned',
  },
  {
    key: 'labOperations',
    number: 9,
    title: 'Lab / Operations',
    description: 'Lab health, traffic simulator hooks, maintenance windows, operational runbooks, and PTP/SyncE.',
    icon: <FlaskConical className="h-5 w-5" />,
    submenus: ['Lab health', 'Traffic simulator', 'Maintenance', 'Runbooks', 'PTP / SyncE'],
    status: 'planned',
  },
];

function GeneralPanel() {
  const { theme, setTheme } = useThemeStore();
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Appearance" />
        <div className="space-y-4 p-4">
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Theme</span>
            <Select
              value={theme}
              onChange={(e) => setTheme(e.target.value as Theme)}
              className="max-w-xs"
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </Select>
          </label>
        </div>
      </Card>
      <Card>
        <CardHeader title="Polling (read-only)" />
        <dl className="grid grid-cols-1 gap-3 p-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-gray-500">KPI poll interval</dt>
            <dd>60s (backend env: <code>POLL_INTERVAL</code>)</dd>
          </div>
          <div>
            <dt className="text-gray-500">Topology poll interval</dt>
            <dd>300s (<code>TOPOLOGY_POLL_INTERVAL</code>)</dd>
          </div>
          <div>
            <dt className="text-gray-500">Alarm poll interval</dt>
            <dd>30s (<code>ALARM_POLL_INTERVAL</code>)</dd>
          </div>
          <div>
            <dt className="text-gray-500">Polling workers</dt>
            <dd>4 (<code>POLL_WORKERS</code>)</dd>
          </div>
        </dl>
      </Card>
      <Card>
        <CardHeader title="cisco.com / TAC" />
        <p className="p-4 text-sm text-gray-500">
          Coming soon: cisco.com credentials, software update channel, TAC contact information.
        </p>
      </Card>
    </div>
  );
}

interface SecuritySettings {
  https_enabled: boolean;
  https_redirect_enabled: boolean;
  tls_min_version: 'TLSv1.2' | 'TLSv1.3';
  tls_cert_file: string;
  tls_key_file: string;
  tls_ca_file: string;
  require_signed_html_certificate: boolean;
  api_auth_enabled: boolean;
  max_parallel_sessions: number;
  idle_timeout_minutes: number;
  root_web_login_enabled: boolean;
}

interface AppUser {
  id: string;
  username: string;
  display_name?: string | null;
  role: string;
  roles?: string[];
  user_type: string;
  custom_permissions: Record<string, boolean>;
  virtual_domain?: string | null;
  enabled: boolean;
  force_password_change: boolean;
}

interface AppRole {
  id: string;
  name: string;
  display_name?: string | null;
  description?: string | null;
  user_type: string;
  permissions: Record<string, boolean>;
  built_in: boolean;
  editable?: boolean;
}

type PermissionCatalog = Record<string, { key: string; label: string; description?: string }[]>;

interface SystemSettingsPermission {
  task_group: string;
  task_name: string;
  additional_permission: string;
  permission_key: string;
}

const EMPTY_USER_FORM = {
  username: '',
  display_name: '',
  first_name: '',
  last_name: '',
  description: '',
  email: '',
  password: '',
  confirm_password: '',
  role: 'admin',
  roles: ['admin'] as string[],
  user_type: 'web',
  virtual_domain: 'all-domain',
  custom_permissions: {} as Record<string, boolean>,
};

type NewUserForm = typeof EMPTY_USER_FORM;
type UserFormField = keyof Pick<NewUserForm, 'username' | 'first_name' | 'last_name' | 'email' | 'password' | 'confirm_password' | 'roles'>;
type UserFormErrors = Partial<Record<UserFormField, string>>;

const USERNAME_PATTERN = /^[A-Za-z0-9_.@-]+$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function passwordRuleChecks(user: NewUserForm) {
  const password = user.password;
  const identityParts = [user.username, user.email, user.first_name, user.last_name]
    .map((part) => part.trim().toLowerCase())
    .filter((part) => part.length >= 3);
  const lowerPassword = password.toLowerCase();

  return [
    { key: 'length', label: 'At least 12 characters', valid: password.length >= 12 },
    { key: 'uppercase', label: 'At least one uppercase letter', valid: /[A-Z]/.test(password) },
    { key: 'lowercase', label: 'At least one lowercase letter', valid: /[a-z]/.test(password) },
    { key: 'number', label: 'At least one number', valid: /\d/.test(password) },
    { key: 'special', label: 'At least one special character', valid: /[^A-Za-z0-9\s]/.test(password) },
    { key: 'space', label: 'No spaces or line breaks', valid: password.length > 0 && !/\s/.test(password) },
    {
      key: 'identity',
      label: 'Must not contain username, email, first name, or last name',
      valid: password.length > 0 && !identityParts.some((part) => lowerPassword.includes(part)),
    },
  ];
}

function validateNewUser(user: NewUserForm): UserFormErrors {
  const errors: UserFormErrors = {};
  const username = user.username.trim();
  const firstName = user.first_name.trim();
  const lastName = user.last_name.trim();
  const email = user.email.trim();

  if (!username) errors.username = 'User name is required.';
  else if (username.length < 3) errors.username = 'User name must be at least 3 characters.';
  else if (!USERNAME_PATTERN.test(username)) errors.username = 'Use only letters, numbers, underscore, dot, at sign, or dash.';

  if (!firstName) errors.first_name = 'First name is required.';
  if (!lastName) errors.last_name = 'Last name is required.';
  if (!email) errors.email = 'Email address is required.';
  else if (!EMAIL_PATTERN.test(email)) errors.email = 'Enter a valid email address.';

  const failedPasswordRule = passwordRuleChecks(user).find((rule) => !rule.valid);
  if (!user.password) errors.password = 'Password is required.';
  else if (failedPasswordRule) errors.password = failedPasswordRule.label;

  if (!user.confirm_password) errors.confirm_password = 'Confirm the password.';
  else if (user.password !== user.confirm_password) errors.confirm_password = 'Passwords do not match.';

  if (user.roles.length === 0) errors.roles = 'Select at least one role.';

  return errors;
}

function apiValidationErrors(error: unknown): UserFormErrors {
  if (typeof error !== 'object' || error === null || !('response' in error)) return {};
  const response = (error as { response?: { data?: { detail?: unknown } } }).response;
  const detail = response?.data?.detail;
  if (!Array.isArray(detail)) return {};

  const errors: UserFormErrors = {};
  for (const item of detail) {
    if (typeof item !== 'object' || item === null) continue;
    const loc = (item as { loc?: unknown }).loc;
    const msg = (item as { msg?: unknown }).msg;
    if (!Array.isArray(loc) || typeof msg !== 'string') continue;
    const field = loc[loc.length - 1];
    let target: UserFormField | null = null;
    if (field === 'username' || field === 'password' || field === 'roles') target = field;
    if (field === 'role' || field === 'user_type' || field === 'virtual_domain') target = 'roles';
    if (target) errors[target] = msg;
  }
  return errors;
}

function PasswordPolicyFloat({ user, visible }: { user: NewUserForm; visible: boolean }) {
  if (!visible) return null;
  const checks = passwordRuleChecks(user);
  return (
    <div className="absolute left-0 top-full z-40 mt-2 w-full rounded-lg border border-gray-200 bg-white p-3 text-xs shadow-xl dark:border-gray-700 dark:bg-gray-900 md:left-[calc(100%+0.75rem)] md:top-0 md:mt-0 md:w-80">
      <div className="mb-2 font-semibold text-gray-900 dark:text-gray-100">Password rules</div>
      <ul className="space-y-1.5">
        {checks.map((rule) => (
          <li key={rule.key} className={`flex items-center gap-2 ${rule.valid ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
            {rule.valid ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
            <span>{rule.label}</span>
          </li>
        ))}
      </ul>
      <div className="mt-2 rounded bg-amber-50 px-2 py-1 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
        Security tip: do not reuse device, TACACS/RADIUS, or personal account passwords.
      </div>
    </div>
  );
}

function InfoFloat({ title, description }: { title: string; description?: string }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  const show = () => {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (rect) {
      setPos({
        top: Math.min(rect.top, window.innerHeight - 160),
        left: Math.min(rect.right + 8, window.innerWidth - 304),
      });
    }
    setOpen(true);
  };

  return (
    <span className="inline-block">
      <button
        ref={buttonRef}
        type="button"
        onMouseEnter={show}
        onMouseLeave={() => setOpen(false)}
        onFocus={show}
        onBlur={() => setOpen(false)}
        onClick={() => (open ? setOpen(false) : show())}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-cisco-blue/10 text-cisco-blue hover:bg-cisco-blue/20"
        aria-label={`Info about ${title}`}
      >
        <Info className="h-3 w-3" />
      </button>
      {open && createPortal(
        <span
          className="fixed z-[9999] w-72 rounded-lg border border-gray-200 bg-white p-3 text-xs shadow-xl dark:border-gray-700 dark:bg-gray-900"
          style={{ top: pos.top, left: pos.left }}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
        >
          <span className="block font-semibold text-gray-900 dark:text-gray-100">{title}</span>
          <span className="mt-1 block text-gray-600 dark:text-gray-300">
            {description || 'No description provided.'}
          </span>
        </span>,
        document.body,
      )}
    </span>
  );
}

function ClientsUsersPanel({ mode = 'full' }: { mode?: 'full' | 'security' | 'users' }) {
  const [security, setSecurity] = useState<SecuritySettings | null>(null);
  const [users, setUsers] = useState<AppUser[]>([]);
  const [roles, setRoles] = useState<AppRole[]>([]);
  const [catalog, setCatalog] = useState<PermissionCatalog>({});
  const [systemSettingsPerms, setSystemSettingsPerms] = useState<SystemSettingsPermission[]>([]);
  const [newUser, setNewUser] = useState({ ...EMPTY_USER_FORM });
  const [userFormErrors, setUserFormErrors] = useState<UserFormErrors>({});
  const [passwordHelpOpen, setPasswordHelpOpen] = useState(false);
  const [newRole, setNewRole] = useState({ name: '', description: '', user_type: 'web', permissions: {} as Record<string, boolean> });
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState<'users' | 'roles' | 'sessions'>(mode === 'security' ? 'sessions' : 'users');
  const [showNewUser, setShowNewUser] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [roleSubTab, setRoleSubTab] = useState<'tasks' | 'members'>('tasks');
  const [roleFilter, setRoleFilter] = useState('');
  const [roleDropdownOpen, setRoleDropdownOpen] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});

  const toggleCategory = (cat: string) =>
    setExpandedCategories((prev) => ({ ...prev, [cat]: !prev[cat] }));

  useEffect(() => {
    void Promise.all([
      api.get('/settings/security').then((r) => setSecurity(r.data)),
      api.get('/settings/users').then((r) => setUsers(r.data)),
      api.get('/settings/roles').then((r) => setRoles(r.data)).then(() => {}),
      api.get('/settings/permissions').then((r) => setCatalog(r.data)),
      api.get('/settings/permissions/system-settings').then((r) => setSystemSettingsPerms(r.data)).catch(() => setSystemSettingsPerms([])),
    ]);
  }, []);

  useEffect(() => {
    if (!selectedRoleId && roles.length) setSelectedRoleId(roles[0].id);
  }, [roles, selectedRoleId]);

  const updateSecurity = <K extends keyof SecuritySettings>(key: K, value: SecuritySettings[K]) => {
    setSecurity((prev) => prev ? { ...prev, [key]: value } : prev);
  };

  const saveSecurity = async () => {
    if (!security) return;
    setSaving(true);
    try {
      const response = await api.patch('/settings/security', security);
      setSecurity(response.data);
    } finally {
      setSaving(false);
    }
  };

  const createUser = async () => {
    const validationErrors = validateNewUser(newUser);
    setUserFormErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      window.alert('Please fix the highlighted user fields before saving.');
      setPasswordHelpOpen(!!validationErrors.password);
      return;
    }

    const payload = {
      username: newUser.username.trim(),
      password: newUser.password,
      role: newUser.roles[0] || newUser.role,
      roles: newUser.roles,
      user_type: newUser.user_type,
      virtual_domain: newUser.virtual_domain && newUser.virtual_domain !== 'all-domain' ? newUser.virtual_domain : null,
      display_name: newUser.display_name || `${newUser.first_name} ${newUser.last_name}`.trim() || newUser.username,
      custom_permissions: newUser.custom_permissions,
    };
    try {
      const response = await api.post('/settings/users', payload);
      setUsers((prev) => [...prev, response.data]);
      setNewUser({ ...EMPTY_USER_FORM });
      setUserFormErrors({});
      setPasswordHelpOpen(false);
      setShowNewUser(false);
    } catch (error) {
      const fieldErrors = apiValidationErrors(error);
      setUserFormErrors(fieldErrors);
      if (fieldErrors.password) setPasswordHelpOpen(true);
      window.alert(Object.keys(fieldErrors).length ? 'Please fix the highlighted user fields before saving.' : 'User could not be saved. Check the field values and try again.');
    }
  };

  const createRole = async () => {
    if (!newRole.name) return;
    const response = await api.post('/settings/roles', newRole);
    setRoles((prev) => [...prev, response.data]);
    setNewRole({ name: '', description: '', user_type: 'web', permissions: {} });
  };

  const toggleSelectedRolePermission = async (roleId: string, key: string) => {
    const role = roles.find((r) => r.id === roleId);
    if (!role) return;
    if (role.built_in && role.editable === false) return;
    const nextPerms = { ...role.permissions, [key]: !role.permissions[key] };
    const response = await api.patch(`/settings/roles/${roleId}`, { permissions: nextPerms });
    setRoles((prev) => prev.map((r) => (r.id === roleId ? response.data : r)));
  };

  const toggleUserPermission = (key: string) => {
    setNewUser((prev) => ({ ...prev, custom_permissions: { ...prev.custom_permissions, [key]: !prev.custom_permissions[key] } }));
  };

  const roleMenuOrder = ['root', 'super_users', 'admin', 'config_managers', 'system_monitoring', 'user_defined_1', 'user_defined_2', 'user_defined_3', 'user_defined_4', 'user_defined_5', 'monitor_lite', 'nbi_read', 'nbi_write'];
  const selectableRoles = roleMenuOrder.map((name) => roles.find((role) => role.name === name)).filter(Boolean) as AppRole[];

  const toggleUserRole = (role: AppRole) => {
    setUserFormErrors((prev) => ({ ...prev, roles: undefined }));
    setNewUser((prev) => {
      const current = new Set(prev.roles);
      if (current.has(role.name)) current.delete(role.name);
      else {
        if (role.name === 'monitor_lite') current.clear();
        current.add(role.name);
        if (current.has('monitor_lite') && role.name !== 'monitor_lite') current.delete('monitor_lite');
      }
      const nextRoles = Array.from(current);
      const hasNbi = nextRoles.some((name) => roles.find((r) => r.name === name)?.user_type === 'nbi');
      const hasWeb = nextRoles.some((name) => roles.find((r) => r.name === name)?.user_type === 'web');
      return {
        ...prev,
        roles: nextRoles,
        role: nextRoles[0] || '',
        user_type: hasNbi && !hasWeb ? 'nbi' : 'web',
      };
    });
  };

  return (
    <div className="space-y-6">
      {mode !== 'users' && (
      <Card>
        <CardHeader title="HTTPS / TLS and Certificates" />
        {security && (
          <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={security.https_enabled} onChange={(e) => updateSecurity('https_enabled', e.target.checked)} />
              Enable HTTPS for application access
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={security.https_redirect_enabled} onChange={(e) => updateSecurity('https_redirect_enabled', e.target.checked)} />
              Redirect HTTP to HTTPS
            </label>
            <label>
              <span className="mb-1 block font-medium">Minimum TLS Version</span>
              <Select value={security.tls_min_version} onChange={(e) => updateSecurity('tls_min_version', e.target.value as SecuritySettings['tls_min_version'])}>
                <option value="TLSv1.3">TLSv1.3</option>
                <option value="TLSv1.2">TLSv1.2</option>
              </Select>
            </label>
            <label className="flex items-center gap-2 md:mt-6">
              <input type="checkbox" checked={security.require_signed_html_certificate} onChange={(e) => updateSecurity('require_signed_html_certificate', e.target.checked)} />
              Require signed certificate for HTML UI
            </label>
            <label>
              <span className="mb-1 block font-medium">Certificate file</span>
              <Input value={security.tls_cert_file} onChange={(e) => updateSecurity('tls_cert_file', e.target.value)} placeholder="/certs/server.crt" />
            </label>
            <label>
              <span className="mb-1 block font-medium">Private key file</span>
              <Input value={security.tls_key_file} onChange={(e) => updateSecurity('tls_key_file', e.target.value)} placeholder="/certs/server.key" />
            </label>
            <label>
              <span className="mb-1 block font-medium">CA bundle / chain file</span>
              <Input value={security.tls_ca_file} onChange={(e) => updateSecurity('tls_ca_file', e.target.value)} placeholder="/certs/ca-chain.crt" />
            </label>
            <div className="flex items-end justify-end">
              <Button onClick={saveSecurity} disabled={saving}>{saving ? 'Saving...' : 'Save TLS Settings'}</Button>
            </div>
          </div>
        )}
      </Card>
      )}

      <Card>
        <CardHeader title={mode === 'security' ? 'Application Access and Sessions' : 'Application Access and User Permissions'} />
        {mode !== 'users' && security && (
          <div className="grid grid-cols-1 gap-4 border-b border-gray-200 p-4 text-sm dark:border-gray-700 md:grid-cols-3">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={security.api_auth_enabled} onChange={(e) => updateSecurity('api_auth_enabled', e.target.checked)} />
              Require API authentication
            </label>
            <label>
              <span className="mb-1 block font-medium">Parallel sessions</span>
              <Input type="number" value={security.max_parallel_sessions} onChange={(e) => updateSecurity('max_parallel_sessions', Number(e.target.value))} />
            </label>
            <label>
              <span className="mb-1 block font-medium">Idle timeout (minutes)</span>
              <Input type="number" value={security.idle_timeout_minutes} onChange={(e) => updateSecurity('idle_timeout_minutes', Number(e.target.value))} />
            </label>
            <label className="flex items-center gap-2 md:col-span-2">
              <input type="checkbox" checked={security.root_web_login_enabled} onChange={(e) => updateSecurity('root_web_login_enabled', e.target.checked)} />
              Allow web GUI root login (Cisco-style recommendation: disable after creating an Admin/Super User)
            </label>
          </div>
        )}

        {mode === 'security' && (
          <div className="p-4 text-sm text-gray-500">
            Active session inventory and token revocation are pending. Current limits are saved through the live security settings API above.
          </div>
        )}

        {mode !== 'security' && (
        <div className="p-0">
          <div className="flex border-b border-gray-200 dark:border-gray-700">
            {([
              ['users', 'Users'],
              ['roles', 'Roles'],
              ['sessions', 'Active Sessions'],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  tab === key
                    ? 'border-cisco-blue text-cisco-blue'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === 'users' && (
            <div className="p-4">
              {!showNewUser ? (
                <div className="mb-4 flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Local Web GUI / NBI Users</h4>
                  <Button onClick={() => setShowNewUser(true)}>+ Create New User</Button>
                </div>
              ) : (
                <div className="mb-4">
                  <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">Create New User</h3>
                  <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    <div className="space-y-3 text-sm">
                      <label className="block">
                        <span className="mb-1 block font-medium">User Name <span className="text-red-500">*</span></span>
                        <Input value={newUser.username} error={userFormErrors.username} onChange={(e) => { setNewUser((p) => ({ ...p, username: e.target.value })); setUserFormErrors((p) => ({ ...p, username: undefined })); }} />
                      </label>
                      <label className="block">
                        <span className="mb-1 block font-medium">First Name <span className="text-red-500">*</span></span>
                        <Input value={newUser.first_name} error={userFormErrors.first_name} onChange={(e) => { setNewUser((p) => ({ ...p, first_name: e.target.value })); setUserFormErrors((p) => ({ ...p, first_name: undefined })); }} />
                      </label>
                      <label className="block">
                        <span className="mb-1 block font-medium">Last Name <span className="text-red-500">*</span></span>
                        <Input value={newUser.last_name} error={userFormErrors.last_name} onChange={(e) => { setNewUser((p) => ({ ...p, last_name: e.target.value })); setUserFormErrors((p) => ({ ...p, last_name: undefined })); }} />
                      </label>
                      <label className="block">
                        <span className="mb-1 block font-medium">Description</span>
                        <Input value={newUser.description} onChange={(e) => setNewUser((p) => ({ ...p, description: e.target.value }))} />
                      </label>
                      <label className="block">
                        <span className="mb-1 block font-medium">Email Address <span className="text-red-500">*</span></span>
                        <Input type="email" value={newUser.email} error={userFormErrors.email} onChange={(e) => { setNewUser((p) => ({ ...p, email: e.target.value })); setUserFormErrors((p) => ({ ...p, email: undefined })); }} />
                      </label>
                      <label className="block">
                        <span className="mb-1 block font-medium">Role <span className="text-red-500">*</span></span>
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => setRoleDropdownOpen((open) => !open)}
                            className="flex w-full items-center justify-between rounded-md border border-gray-300 bg-white px-3 py-2 text-left text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-cisco-blue dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                          >
                            <span className="truncate">
                              {newUser.roles.length
                                ? newUser.roles.map((name) => roles.find((r) => r.name === name)?.display_name || name).join(', ')
                                : 'Select roles'}
                            </span>
                            <ChevronRight className={`h-4 w-4 transition-transform ${roleDropdownOpen ? 'rotate-90' : ''}`} />
                          </button>
                          {roleDropdownOpen && (
                            <div className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-900">
                              {selectableRoles.map((role) => (
                                <label key={role.id} className="flex cursor-pointer items-start gap-2 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800">
                                  <input
                                    type="checkbox"
                                    checked={newUser.roles.includes(role.name)}
                                    onChange={() => toggleUserRole(role)}
                                    className="mt-0.5"
                                  />
                                  <span className="min-w-0 flex-1">
                                    <span className="block font-medium text-gray-900 dark:text-gray-100">{role.display_name || role.name}</span>
                                    <span className="block text-xs text-gray-500">{role.user_type === 'nbi' ? 'NBI' : 'Web UI'} · {role.description}</span>
                                  </span>
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                        {userFormErrors.roles && <span className="mt-1 block text-xs text-severity-critical">{userFormErrors.roles}</span>}
                        <span className="mt-1 block text-xs text-gray-500">
                          Monitor Lite is exclusive. Web UI and NBI roles come from Roles.csv.
                        </span>
                      </label>
                      <label className="block">
                        <span className="mb-1 block font-medium">User Type</span>
                        <Select value={newUser.user_type} onChange={(e) => setNewUser((p) => ({ ...p, user_type: e.target.value }))}>
                          <option value="web">Web GUI</option>
                          <option value="nbi">NBI REST API</option>
                        </Select>
                      </label>
                      <label className="relative block">
                        <span className="mb-1 flex items-center gap-2 font-medium">
                          Password <span className="text-red-500">*</span>
                          <InfoFloat title="Password rules" description="Use a unique password with at least 12 characters, uppercase and lowercase letters, a number, a special character, no spaces, and no username/name/email fragments." />
                        </span>
                        <Input
                          type="password"
                          value={newUser.password}
                          error={userFormErrors.password}
                          onFocus={() => setPasswordHelpOpen(true)}
                          onBlur={() => setPasswordHelpOpen(false)}
                          onChange={(e) => {
                            setNewUser((p) => ({ ...p, password: e.target.value }));
                            setUserFormErrors((p) => ({ ...p, password: undefined, confirm_password: undefined }));
                          }}
                        />
                        <PasswordPolicyFloat user={newUser} visible={passwordHelpOpen || !!userFormErrors.password} />
                      </label>
                      <label className="block">
                        <span className="mb-1 block font-medium">Confirm Password <span className="text-red-500">*</span></span>
                        <Input
                          type="password"
                          value={newUser.confirm_password}
                          error={userFormErrors.confirm_password}
                          onChange={(e) => {
                            setNewUser((p) => ({ ...p, confirm_password: e.target.value }));
                            setUserFormErrors((p) => ({ ...p, confirm_password: undefined }));
                          }}
                        />
                      </label>
                      <div className="flex gap-2 pt-2">
                        <Button onClick={createUser}>Save</Button>
                        <Button variant="secondary" onClick={() => { setShowNewUser(false); setNewUser({ ...EMPTY_USER_FORM }); setUserFormErrors({}); setPasswordHelpOpen(false); }}>Cancel</Button>
                      </div>
                    </div>
                    <div>
                      <h4 className="mb-2 text-sm font-semibold">Scope</h4>
                      <div className="rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-700">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-medium">all-domain</div>
                            <div className="text-xs text-gray-500">
                              User has access to every device managed by this server. Virtual domains can be created later under Virtual Domain Management and assigned per user.
                            </div>
                          </div>
                          <Badge variant="success">Default</Badge>
                        </div>
                      </div>

                      <div className="mt-4 rounded-lg border border-gray-200 dark:border-gray-700">
                        <div className="border-b border-gray-200 bg-gray-50 px-3 py-2 text-sm font-semibold dark:border-gray-700 dark:bg-gray-800">
                          Optional per-user privilege overrides
                          <span className="ml-2 text-xs font-normal text-gray-500">
                            Check items to grant extra privileges on top of the selected role.
                          </span>
                        </div>
                        <div className="max-h-96 overflow-y-auto p-3">
                          {Object.entries(catalog).map(([group, permissions]) => (
                            <div key={group} className="mb-3">
                              <div className="mb-1 text-xs font-semibold uppercase text-gray-500">{group}</div>
                              {permissions.map((permission) => (
                                <label key={permission.key} className="flex items-center gap-2 py-0.5 text-xs">
                                  <input
                                    type="checkbox"
                                    checked={!!newUser.custom_permissions[permission.key]}
                                    onChange={() => toggleUserPermission(permission.key)}
                                  />
                                  <span className="flex-1">{permission.label}</span>
                                  <InfoFloat title={permission.label} description={permission.description} />
                                </label>
                              ))}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
                <table className="min-w-full text-sm text-gray-700 dark:text-gray-200">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      {['Username', 'Type', 'Role', 'Virtual Domain', 'Overrides', 'Status'].map((h) => <th key={h} className="px-4 py-2 text-left text-xs uppercase text-gray-500 dark:text-gray-400">{h}</th>)}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {users.map((user) => (
                      <tr key={user.id}>
                        <td className="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{user.username}</td>
                        <td className="px-4 py-2">{user.user_type === 'nbi' ? 'NBI REST API' : 'Web GUI'}</td>
                        <td className="px-4 py-2">{(user.roles?.length ? user.roles : user.role.split(',')).map((name) => roles.find((r) => r.name === name)?.display_name || name).join(', ')}</td>
                        <td className="px-4 py-2">{user.virtual_domain || 'all-domain'}</td>
                        <td className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400">{Object.values(user.custom_permissions || {}).filter(Boolean).length}</td>
                        <td className="px-4 py-2"><Badge variant={user.enabled ? 'success' : 'neutral'}>{user.enabled ? 'Enabled' : 'Disabled'}</Badge></td>
                      </tr>
                    ))}
                    {users.length === 0 && <tr><td className="px-4 py-4 text-gray-500" colSpan={6}>No local users configured.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === 'roles' && (
            <div className="grid grid-cols-12 gap-0">
              <aside className="col-span-12 border-r border-gray-200 dark:border-gray-700 md:col-span-3">
                <div className="p-3">
                  <h4 className="mb-2 text-sm font-semibold">Roles</h4>
                  <div className="max-h-[420px] overflow-y-auto">
                    {roles.map((role) => (
                      <button
                        key={role.id}
                        onClick={() => setSelectedRoleId(role.id)}
                        className={`block w-full truncate rounded px-3 py-2 text-left text-sm ${
                          selectedRoleId === role.id ? 'bg-cisco-blue/10 font-semibold text-cisco-blue' : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                        }`}
                        title={role.description || ''}
                      >
                        <span>{role.display_name || role.name}</span>
                        <span className="ml-1 text-xs text-gray-400">{role.user_type === 'nbi' ? '(NBI)' : ''}</span>
                      </button>
                    ))}
                  </div>
                  <div className="mt-3 space-y-2 border-t border-gray-200 pt-3 dark:border-gray-700">
                    <Input placeholder="new role name" value={newRole.name} onChange={(e) => setNewRole((p) => ({ ...p, name: e.target.value }))} />
                    <Input placeholder="description" value={newRole.description} onChange={(e) => setNewRole((p) => ({ ...p, description: e.target.value }))} />
                    <Button onClick={createRole} className="w-full">+ Add Custom Role</Button>
                  </div>
                </div>
              </aside>
              <section className="col-span-12 md:col-span-9">
                {selectedRoleId && (() => {
                  const role = roles.find((r) => r.id === selectedRoleId);
                  if (!role) return null;
                  return (
                    <div>
                      <div className="border-b border-gray-200 p-3 dark:border-gray-700">
                        <div className="flex items-center gap-2">
                          <h4 className="text-base font-semibold">Role Permissions ({role.display_name || role.name})</h4>
                          <Badge variant={role.built_in ? 'default' : 'success'}>{role.built_in ? 'Built-in' : 'Custom'}</Badge>
                          <Badge variant={role.user_type === 'nbi' ? 'warning' : 'default'}>{role.user_type === 'nbi' ? 'NBI' : 'Web UI'}</Badge>
                          {role.description && <span className="ml-2 text-xs text-gray-500">{role.description}</span>}
                        </div>
                      </div>
                      <div className="flex border-b border-gray-200 dark:border-gray-700">
                        {([
                          ['tasks', 'Task Permissions'],
                          ['members', 'Members'],
                        ] as const).map(([key, label]) => (
                          <button
                            key={key}
                            onClick={() => setRoleSubTab(key)}
                            className={`px-4 py-2 text-sm font-medium border-b-2 ${
                              roleSubTab === key ? 'border-cisco-blue text-cisco-blue' : 'border-transparent text-gray-500'
                            }`}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      {roleSubTab === 'tasks' && (() => {
                        const SUBMENU_CAT = 'Additional Permissions for System Settings Submenus';
                        const lockedByWildcard = !!role.permissions['*'];
                        const disabled = role.built_in && role.editable === false;
                        const lf = roleFilter.toLowerCase();

                        // Build submenu lookup keyed by permission_key
                        const submenuByKey = Object.fromEntries(
                          systemSettingsPerms.map((sp) => [sp.permission_key, sp.additional_permission])
                        );

                        // Separate submenu category from regular categories
                        const regularCats = Object.entries(catalog).filter(([g]) => g !== SUBMENU_CAT);
                        const submenuCat = catalog[SUBMENU_CAT] ?? [];

                        const renderRow = (p: { key: string; label: string; description?: string }, isSubmenu = false) => {
                          const checked = lockedByWildcard || !!role.permissions[p.key];
                          const addlPerm = submenuByKey[p.key] || '';
                          const infoDesc = isSubmenu
                            ? `Additional permission required: ${addlPerm}`
                            : (p.description || '');
                          return (
                            <div key={p.key} className="flex items-center gap-2 border-b border-gray-100 px-3 py-1.5 last:border-0 dark:border-gray-800">
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={disabled}
                                onChange={() => toggleSelectedRolePermission(role.id, p.key)}
                                className="shrink-0"
                              />
                              <span className="flex-1 text-sm">{p.label}</span>
                              {isSubmenu && addlPerm && (
                                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                                  {addlPerm}
                                </span>
                              )}
                              <InfoFloat title={p.label} description={infoDesc} />
                            </div>
                          );
                        };

                        return (
                          <div className="p-3">
                            <Input
                              placeholder="Filter by task name or category..."
                              value={roleFilter}
                              onChange={(e) => setRoleFilter(e.target.value)}
                              className="mb-3 max-w-md"
                            />
                            <div className="max-h-[560px] space-y-1 overflow-y-auto">
                              {/* Regular task categories */}
                              {regularCats.map(([group, perms]) => {
                                const filtered = perms.filter(
                                  (p) => !lf || p.label.toLowerCase().includes(lf) || group.toLowerCase().includes(lf)
                                );
                                if (!filtered.length) return null;
                                const enabledCount = filtered.filter(
                                  (p) => lockedByWildcard || !!role.permissions[p.key]
                                ).length;
                                const isOpen = expandedCategories[group] ?? false;
                                return (
                                  <div key={group} className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
                                    <button
                                      type="button"
                                      onClick={() => toggleCategory(group)}
                                      className="flex w-full items-center justify-between bg-gray-50 px-3 py-2 text-left text-sm font-semibold text-gray-700 hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
                                    >
                                      <span>{group}</span>
                                      <span className="flex items-center gap-2">
                                        <span className="rounded-full bg-cisco-blue/10 px-2 py-0.5 text-xs text-cisco-blue">
                                          {enabledCount}/{filtered.length}
                                        </span>
                                        <ChevronRight className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
                                      </span>
                                    </button>
                                    {isOpen && (
                                      <div>{filtered.map((p) => renderRow(p))}</div>
                                    )}
                                  </div>
                                );
                              })}

                              {/* Special category: Additional Permissions for System Settings Submenus */}
                              {submenuCat.length > 0 && (() => {
                                const filtered = submenuCat.filter(
                                  (p) => !lf || p.label.toLowerCase().includes(lf) || SUBMENU_CAT.toLowerCase().includes(lf)
                                );
                                if (!filtered.length) return null;
                                const enabledCount = filtered.filter(
                                  (p) => lockedByWildcard || !!role.permissions[p.key]
                                ).length;
                                const isOpen = expandedCategories[SUBMENU_CAT] ?? false;
                                return (
                                  <div className="overflow-hidden rounded-lg border-2 border-amber-400 dark:border-amber-600">
                                    <button
                                      type="button"
                                      onClick={() => toggleCategory(SUBMENU_CAT)}
                                      className="flex w-full items-center justify-between bg-amber-50 px-3 py-2 text-left text-sm font-semibold text-amber-800 hover:bg-amber-100 dark:bg-amber-900/20 dark:text-amber-300 dark:hover:bg-amber-900/30"
                                    >
                                      <span className="flex items-center gap-2">
                                        <span className="rounded bg-amber-200 px-1.5 py-0.5 text-xs font-bold text-amber-800 dark:bg-amber-800 dark:text-amber-200">
                                          Table 2
                                        </span>
                                        Additional Permissions for System Settings Submenus
                                      </span>
                                      <span className="flex items-center gap-2">
                                        <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-800 dark:text-amber-200">
                                          {enabledCount}/{filtered.length}
                                        </span>
                                        <ChevronRight className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
                                      </span>
                                    </button>
                                    {isOpen && (
                                      <div className="bg-amber-50/50 dark:bg-amber-900/10">
                                        {filtered.map((p) => renderRow(p, true))}
                                      </div>
                                    )}
                                  </div>
                                );
                              })()}
                            </div>
                          </div>
                        );
                      })()}
                      {roleSubTab === 'members' && (
                        <div className="p-3">
                          <table className="min-w-full text-sm">
                            <thead className="bg-gray-50 dark:bg-gray-800">
                              <tr>
                                <th className="px-3 py-2 text-left text-xs uppercase text-gray-500">Username</th>
                                <th className="px-3 py-2 text-left text-xs uppercase text-gray-500">Type</th>
                                <th className="px-3 py-2 text-left text-xs uppercase text-gray-500">Status</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                              {users.filter((u) => (u.roles?.length ? u.roles : u.role.split(',')).includes(role.name)).map((u) => (
                                <tr key={u.id}>
                                  <td className="px-3 py-2 font-medium">{u.username}</td>
                                  <td className="px-3 py-2">{u.user_type === 'nbi' ? 'NBI' : 'Web GUI'}</td>
                                  <td className="px-3 py-2"><Badge variant={u.enabled ? 'success' : 'neutral'}>{u.enabled ? 'Enabled' : 'Disabled'}</Badge></td>
                                </tr>
                              ))}
                              {users.filter((u) => (u.roles?.length ? u.roles : u.role.split(',')).includes(role.name)).length === 0 && (
                                <tr><td className="px-3 py-3 text-gray-500" colSpan={3}>No members assigned to this role.</td></tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </section>
            </div>
          )}

          {tab === 'sessions' && (
            <div className="p-4 text-sm text-gray-500">
              Active session tracking coming soon. Session timeout and concurrent session limits are configured in the Security submenu.
            </div>
          )}
        </div>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// System panel: mail / jobs / retention
// ---------------------------------------------------------------------------

interface SystemMailCfg { smtp_host: string; smtp_port: number; smtp_from: string; smtp_use_tls: boolean; smtp_username: string; }
interface SystemJobsCfg { job_concurrency: number; job_retry_backoff_seconds: number; job_max_retries: number; }
interface SystemRetentionCfg { alarm_retention_days: number; event_retention_days: number; kpi_retention_days: number; telemetry_sample_retention_days: number; }
interface SystemAdminSettings { mail: SystemMailCfg; jobs: SystemJobsCfg; retention: SystemRetentionCfg; }

const SYSTEM_DEFAULTS: SystemAdminSettings = {
  mail: { smtp_host: '', smtp_port: 587, smtp_from: '', smtp_use_tls: true, smtp_username: '' },
  jobs: { job_concurrency: 4, job_retry_backoff_seconds: 30, job_max_retries: 3 },
  retention: { alarm_retention_days: 90, event_retention_days: 30, kpi_retention_days: 365, telemetry_sample_retention_days: 7 },
};

function SystemPanel() {
  const [cfg, setCfg] = useState<SystemAdminSettings>(SYSTEM_DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get('/settings/system').then((r) => setCfg(r.data)).catch(() => {});
  }, []);

  const setMail = <K extends keyof SystemMailCfg>(k: K, v: SystemMailCfg[K]) =>
    setCfg((p) => ({ ...p, mail: { ...p.mail, [k]: v } }));
  const setJobs = <K extends keyof SystemJobsCfg>(k: K, v: SystemJobsCfg[K]) =>
    setCfg((p) => ({ ...p, jobs: { ...p.jobs, [k]: v } }));
  const setRetention = <K extends keyof SystemRetentionCfg>(k: K, v: SystemRetentionCfg[K]) =>
    setCfg((p) => ({ ...p, retention: { ...p.retention, [k]: v } }));

  const save = async () => {
    setSaving(true); setSaved(false); setError(null);
    try {
      const r = await api.put('/settings/system', cfg);
      setCfg(r.data); setSaved(true);
    } catch { setError('Save failed — check field values.'); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Mail Notifications (SMTP)" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block font-medium">SMTP host</span>
            <Input value={cfg.mail.smtp_host} onChange={(e) => setMail('smtp_host', e.target.value)} placeholder="smtp.example.com" />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">SMTP port</span>
            <Input type="number" value={cfg.mail.smtp_port} onChange={(e) => setMail('smtp_port', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">From address</span>
            <Input type="email" value={cfg.mail.smtp_from} onChange={(e) => setMail('smtp_from', e.target.value)} placeholder="nms@example.com" />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Username</span>
            <Input value={cfg.mail.smtp_username} onChange={(e) => setMail('smtp_username', e.target.value)} placeholder="optional" />
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={cfg.mail.smtp_use_tls} onChange={(e) => setMail('smtp_use_tls', e.target.checked)} />
            Use TLS / STARTTLS
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="Scheduled Jobs" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="block">
            <span className="mb-1 block font-medium">Job concurrency</span>
            <Input type="number" value={cfg.jobs.job_concurrency} onChange={(e) => setJobs('job_concurrency', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Retry backoff (seconds)</span>
            <Input type="number" value={cfg.jobs.job_retry_backoff_seconds} onChange={(e) => setJobs('job_retry_backoff_seconds', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Max retries</span>
            <Input type="number" value={cfg.jobs.job_max_retries} onChange={(e) => setJobs('job_max_retries', Number(e.target.value))} />
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="Data Retention Windows" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          {([
            ['alarm_retention_days', 'Alarm retention (days)'],
            ['event_retention_days', 'Event retention (days)'],
            ['kpi_retention_days', 'KPI retention (days)'],
            ['telemetry_sample_retention_days', 'Telemetry sample retention (days)'],
          ] as [keyof SystemRetentionCfg, string][]).map(([key, label]) => (
            <label key={key} className="block">
              <span className="mb-1 block font-medium">{label}</span>
              <Input type="number" value={cfg.retention[key]} onChange={(e) => setRetention(key, Number(e.target.value))} />
            </label>
          ))}
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save System Settings'}</Button>
        {saved && <span className="text-sm text-green-600">Saved.</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Network Devices panel: CLI / SNMP defaults
// ---------------------------------------------------------------------------

interface NetworkCliCfg { ssh_timeout_seconds: number; ssh_port: number; cli_retries: number; max_concurrent_ssh_sessions: number; terminal_length: number; }
interface NetworkSnmpCfg { snmp_version: 'v2c' | 'v3'; snmp_community: string; snmp_port: number; snmp_timeout_seconds: number; snmp_retries: number; polling_interval_seconds: number; }
interface NetworkDeviceAdminSettings { cli: NetworkCliCfg; snmp: NetworkSnmpCfg; }

const NETWORK_DEFAULTS: NetworkDeviceAdminSettings = {
  cli: { ssh_timeout_seconds: 30, ssh_port: 22, cli_retries: 2, max_concurrent_ssh_sessions: 10, terminal_length: 0 },
  snmp: { snmp_version: 'v2c', snmp_community: 'public', snmp_port: 161, snmp_timeout_seconds: 5, snmp_retries: 2, polling_interval_seconds: 60 },
};

function NetworkDevicesPanel() {
  const [cfg, setCfg] = useState<NetworkDeviceAdminSettings>(NETWORK_DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get('/settings/network-devices').then((r) => setCfg(r.data)).catch(() => {});
  }, []);

  const setCli = <K extends keyof NetworkCliCfg>(k: K, v: NetworkCliCfg[K]) =>
    setCfg((p) => ({ ...p, cli: { ...p.cli, [k]: v } }));
  const setSnmp = <K extends keyof NetworkSnmpCfg>(k: K, v: NetworkSnmpCfg[K]) =>
    setCfg((p) => ({ ...p, snmp: { ...p.snmp, [k]: v } }));

  const save = async () => {
    setSaving(true); setSaved(false); setError(null);
    try {
      const r = await api.put('/settings/network-devices', cfg);
      setCfg(r.data); setSaved(true);
    } catch { setError('Save failed — check field values.'); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="CLI Session Defaults" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block font-medium">SSH timeout (seconds)</span>
            <Input type="number" value={cfg.cli.ssh_timeout_seconds} onChange={(e) => setCli('ssh_timeout_seconds', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">SSH port</span>
            <Input type="number" value={cfg.cli.ssh_port} onChange={(e) => setCli('ssh_port', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">CLI retries</span>
            <Input type="number" value={cfg.cli.cli_retries} onChange={(e) => setCli('cli_retries', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Max concurrent SSH sessions</span>
            <Input type="number" value={cfg.cli.max_concurrent_ssh_sessions} onChange={(e) => setCli('max_concurrent_ssh_sessions', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Terminal length (0 = no-more-prompt)</span>
            <Input type="number" value={cfg.cli.terminal_length} onChange={(e) => setCli('terminal_length', Number(e.target.value))} />
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="SNMP Defaults" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block font-medium">SNMP version</span>
            <Select value={cfg.snmp.snmp_version} onChange={(e) => setSnmp('snmp_version', e.target.value as 'v2c' | 'v3')} className="max-w-xs">
              <option value="v2c">v2c</option>
              <option value="v3">v3</option>
            </Select>
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Community string</span>
            <Input value={cfg.snmp.snmp_community} onChange={(e) => setSnmp('snmp_community', e.target.value)} placeholder="public" />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">SNMP port</span>
            <Input type="number" value={cfg.snmp.snmp_port} onChange={(e) => setSnmp('snmp_port', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Timeout (seconds)</span>
            <Input type="number" value={cfg.snmp.snmp_timeout_seconds} onChange={(e) => setSnmp('snmp_timeout_seconds', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Retries</span>
            <Input type="number" value={cfg.snmp.snmp_retries} onChange={(e) => setSnmp('snmp_retries', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Polling interval (seconds)</span>
            <Input type="number" value={cfg.snmp.polling_interval_seconds} onChange={(e) => setSnmp('polling_interval_seconds', Number(e.target.value))} />
          </label>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save Network Device Settings'}</Button>
        {saved && <span className="text-sm text-green-600">Saved.</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alarms/Events panel: severity / notifications / suppression
// ---------------------------------------------------------------------------

interface AlarmSeverityMapping { critical_oid_value: number; major_oid_value: number; minor_oid_value: number; warning_oid_value: number; info_oid_value: number; }
interface AlarmNotificationCfg { email_enabled: boolean; email_recipients: string; syslog_forward_enabled: boolean; syslog_forward_host: string; syslog_forward_port: number; min_severity_to_notify: string; }
interface AlarmSuppressionCfg { suppression_window_minutes: number; flap_detection_enabled: boolean; flap_threshold_count: number; }
interface AlarmsEventsAdminSettings { severity_mapping: AlarmSeverityMapping; notifications: AlarmNotificationCfg; suppression: AlarmSuppressionCfg; }

const ALARMS_DEFAULTS: AlarmsEventsAdminSettings = {
  severity_mapping: { critical_oid_value: 1, major_oid_value: 2, minor_oid_value: 3, warning_oid_value: 4, info_oid_value: 5 },
  notifications: { email_enabled: false, email_recipients: '', syslog_forward_enabled: false, syslog_forward_host: '', syslog_forward_port: 514, min_severity_to_notify: 'major' },
  suppression: { suppression_window_minutes: 5, flap_detection_enabled: true, flap_threshold_count: 3 },
};

function AlarmsEventsPanel() {
  const [cfg, setCfg] = useState<AlarmsEventsAdminSettings>(ALARMS_DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get('/settings/alarms-events').then((r) => setCfg(r.data)).catch(() => {});
  }, []);

  const setSev = <K extends keyof AlarmSeverityMapping>(k: K, v: number) =>
    setCfg((p) => ({ ...p, severity_mapping: { ...p.severity_mapping, [k]: v } }));
  const setNotif = <K extends keyof AlarmNotificationCfg>(k: K, v: AlarmNotificationCfg[K]) =>
    setCfg((p) => ({ ...p, notifications: { ...p.notifications, [k]: v } }));
  const setSuppr = <K extends keyof AlarmSuppressionCfg>(k: K, v: AlarmSuppressionCfg[K]) =>
    setCfg((p) => ({ ...p, suppression: { ...p.suppression, [k]: v } }));

  const save = async () => {
    setSaving(true); setSaved(false); setError(null);
    try {
      const r = await api.put('/settings/alarms-events', cfg);
      setCfg(r.data); setSaved(true);
    } catch { setError('Save failed — check field values.'); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Severity OID Value Mapping" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          {([
            ['critical_oid_value', 'Critical'],
            ['major_oid_value', 'Major'],
            ['minor_oid_value', 'Minor'],
            ['warning_oid_value', 'Warning'],
            ['info_oid_value', 'Info'],
          ] as [keyof AlarmSeverityMapping, string][]).map(([key, label]) => (
            <label key={key} className="block">
              <span className="mb-1 block font-medium">{label} OID value</span>
              <Input type="number" value={cfg.severity_mapping[key]} onChange={(e) => setSev(key, Number(e.target.value))} />
            </label>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Notification Channels" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="flex items-center gap-2 md:col-span-2">
            <input type="checkbox" checked={cfg.notifications.email_enabled} onChange={(e) => setNotif('email_enabled', e.target.checked)} />
            Enable email notifications
          </label>
          <label className="block md:col-span-2">
            <span className="mb-1 block font-medium">Email recipients (comma-separated)</span>
            <Input value={cfg.notifications.email_recipients} onChange={(e) => setNotif('email_recipients', e.target.value)} placeholder="noc@corp.com, admin@corp.com" disabled={!cfg.notifications.email_enabled} />
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={cfg.notifications.syslog_forward_enabled} onChange={(e) => setNotif('syslog_forward_enabled', e.target.checked)} />
            Forward to syslog server
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Syslog host</span>
            <Input value={cfg.notifications.syslog_forward_host} onChange={(e) => setNotif('syslog_forward_host', e.target.value)} placeholder="syslog.corp.com" disabled={!cfg.notifications.syslog_forward_enabled} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Syslog port</span>
            <Input type="number" value={cfg.notifications.syslog_forward_port} onChange={(e) => setNotif('syslog_forward_port', Number(e.target.value))} disabled={!cfg.notifications.syslog_forward_enabled} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Minimum severity to notify</span>
            <Select value={cfg.notifications.min_severity_to_notify} onChange={(e) => setNotif('min_severity_to_notify', e.target.value)} className="max-w-xs">
              <option value="critical">Critical</option>
              <option value="major">Major</option>
              <option value="minor">Minor</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </Select>
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="Suppression and Flap Detection" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="block">
            <span className="mb-1 block font-medium">Suppression window (minutes)</span>
            <Input type="number" value={cfg.suppression.suppression_window_minutes} onChange={(e) => setSuppr('suppression_window_minutes', Number(e.target.value))} />
          </label>
          <label className="flex items-center gap-2 md:pt-6">
            <input type="checkbox" checked={cfg.suppression.flap_detection_enabled} onChange={(e) => setSuppr('flap_detection_enabled', e.target.checked)} />
            Enable flap detection
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Flap threshold (count)</span>
            <Input type="number" value={cfg.suppression.flap_threshold_count} onChange={(e) => setSuppr('flap_threshold_count', Number(e.target.value))} disabled={!cfg.suppression.flap_detection_enabled} />
          </label>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save Alarms & Events Settings'}</Button>
        {saved && <span className="text-sm text-green-600">Saved.</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  );
}

function PlaceholderPanel({ title, summary, items }: { title: string; summary?: string; items: string[] }) {
  return (
    <Card>
      <CardHeader title={title} />
      <div className="p-4 text-sm">
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          <div className="font-semibold">Phase 1 placeholder</div>
          <p className="mt-1 text-xs">{summary || 'This submenu is intentionally visible now so the Settings IA matches an EPNM-style administrator map before backend forms are added.'}</p>
        </div>
        <p className="mb-3 text-gray-500">Planned administration functions:</p>
        <ul className="grid grid-cols-1 gap-2 text-gray-700 dark:text-gray-300 md:grid-cols-2">
          {items.map((item) => (
            <li key={item} className="rounded border border-gray-200 bg-white p-2 dark:border-gray-700 dark:bg-gray-900">{item}</li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

function CategoryContent({ category }: { category: CategoryKey }) {
  switch (category) {
    case 'general':
      return <GeneralPanel />;
    case 'system':
      return <SystemPanel />;
    case 'security':
      return <ClientsUsersPanel mode="security" />;
    case 'usersRoles':
      return <ClientsUsersPanel mode="users" />;
    case 'networkDevices':
      return <NetworkDevicesPanel />;
    case 'inventory':
      return (
        <PlaceholderPanel
          title="Inventory Administration"
          items={[
            'Configuration archive frequency and retention',
            'Golden image and software image management',
            'Discovery defaults and scope controls',
            'Device group management policies',
            'Lifecycle and compliance metadata',
          ]}
        />
      );
    case 'alarmsEvents':
      return <AlarmsEventsPanel />;
    case 'integrationsAiOps':
      return (
        <PlaceholderPanel
          title="Integrations and AI Ops"
          items={[
            'Northbound API keys and access profiles',
            'Webhook targets and retry policy',
            'AI Ops recommendation thresholds',
            'LLM/model provider settings',
            'Export targets for reports and assurance signals',
          ]}
        />
      );
    case 'labOperations':
      return (
        <PlaceholderPanel
          title="Lab and Operations"
          items={[
            'Lab health defaults and thresholds',
            'Traffic simulator integration hooks',
            'Maintenance windows and blackout calendars',
            'Operational runbook links',
            'PTP / SyncE service settings',
          ]}
        />
      );
  }
}

const SECTION_KEYS = new Set<CategoryKey>([
  'general', 'system', 'security', 'usersRoles', 'networkDevices',
  'inventory', 'alarmsEvents', 'integrationsAiOps', 'labOperations',
]);

function isValidSection(s: string | null): s is CategoryKey {
  return s !== null && SECTION_KEYS.has(s as CategoryKey);
}

function settingsSearchText(category: Category): string {
  return [
    category.title,
    category.description,
    category.status || '',
    ...category.submenus,
  ].join(' ').toLowerCase();
}

function Settings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const sectionParam = searchParams.get('section');
  const [settingsSearch, setSettingsSearch] = useState('');
  const [active, setActive] = useState<CategoryKey>(
    isValidSection(sectionParam) ? sectionParam : 'general',
  );
  const normalizedSearch = settingsSearch.trim().toLowerCase();
  const visibleCategories = normalizedSearch
    ? CATEGORIES.filter((cat) => settingsSearchText(cat).includes(normalizedSearch))
    : CATEGORIES;

  const handleSelect = (key: CategoryKey) => {
    setActive(key);
    setSearchParams({ section: key }, { replace: true });
  };

  // Sync if URL param changes externally (e.g. back/forward navigation).
  useEffect(() => {
    const s = searchParams.get('section');
    if (isValidSection(s) && s !== active) setActive(s);
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="System Settings"
        subtitle="The product allows an administrator to configure or modify the network and system wide settings."
      />

      <div className="grid grid-cols-12 gap-6">
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
            const matchedSubmenus = normalizedSearch
              ? cat.submenus.filter((submenu) => submenu.toLowerCase().includes(normalizedSearch))
              : cat.submenus.slice(0, 3);

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
                    </div>
                    <p className="mt-1 text-xs leading-snug text-gray-600 dark:text-gray-400 line-clamp-3">
                      {cat.description}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(matchedSubmenus.length ? matchedSubmenus : cat.submenus.slice(0, 3)).slice(0, 3).map((submenu) => (
                        <span key={submenu} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                          {submenu}
                        </span>
                      ))}
                      {!normalizedSearch && cat.submenus.length > 3 && (
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-800">
                          +{cat.submenus.length - 3}
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
