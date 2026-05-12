import { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon,
  Mail,
  Network,
  Package,
  Bell,
  Users,
  Cog,
  ChevronRight,
} from 'lucide-react';
import { useThemeStore, type Theme } from '../stores/theme';
import { Card, CardHeader } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';
import { Select } from '../components/ui/Select';
import { Button, Input, Badge } from '../components/ui';
import { api } from '../lib/api';

type CategoryKey =
  | 'general'
  | 'mail'
  | 'network'
  | 'inventory'
  | 'alarms'
  | 'clients'
  | 'services';

interface Category {
  key: CategoryKey;
  number: number;
  title: string;
  description: string;
  icon: React.ReactNode;
}

const CATEGORIES: Category[] = [
  {
    key: 'general',
    number: 1,
    title: 'General',
    description:
      'Configure system wide settings like cisco.com credentials, Database, Jobs, Server Tuning, Software updates and TAC support.',
    icon: <SettingsIcon className="h-5 w-5" />,
  },
  {
    key: 'mail',
    number: 2,
    title: 'Mail and Notifications',
    description: 'Configure the mail server and notification receivers.',
    icon: <Mail className="h-5 w-5" />,
  },
  {
    key: 'network',
    number: 3,
    title: 'Network and Devices',
    description:
      'Configure the network and Device level settings like CLI session, SNMP, Controller Upgrade, Plug & Play.',
    icon: <Network className="h-5 w-5" />,
  },
  {
    key: 'inventory',
    number: 4,
    title: 'Inventory',
    description:
      'Configure inventory functions like configuration, configuration Archives, Image Managements, Group Management, Discovery settings.',
    icon: <Package className="h-5 w-5" />,
  },
  {
    key: 'alarms',
    number: 5,
    title: 'Alarms and Events',
    description:
      'Configure Fault functions like Alarm settings, Severity configurations, System Events, Trap storage, Syslogs, notification receivers.',
    icon: <Bell className="h-5 w-5" />,
  },
  {
    key: 'clients',
    number: 6,
    title: 'Clients and Users',
    description:
      'Configure Clients and Users settings like client trouble shooting, Database settings, Client discovery, OUI.',
    icon: <Users className="h-5 w-5" />,
  },
  {
    key: 'services',
    number: 7,
    title: 'Services',
    description: 'Configure Service functions like PTP/SyncE.',
    icon: <Cog className="h-5 w-5" />,
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
  user_type: string;
  virtual_domain?: string | null;
  enabled: boolean;
  force_password_change: boolean;
}

function ClientsUsersPanel() {
  const [security, setSecurity] = useState<SecuritySettings | null>(null);
  const [users, setUsers] = useState<AppUser[]>([]);
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'viewer', user_type: 'web' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void Promise.all([
      api.get('/settings/security').then((r) => setSecurity(r.data)),
      api.get('/settings/users').then((r) => setUsers(r.data)),
    ]);
  }, []);

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
    if (!newUser.username || !newUser.password) return;
    const response = await api.post('/settings/users', newUser);
    setUsers((prev) => [...prev, response.data]);
    setNewUser({ username: '', password: '', role: 'viewer', user_type: 'web' });
  };

  return (
    <div className="space-y-6">
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

      <Card>
        <CardHeader title="Application Access and User Permissions" />
        {security && (
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

        <div className="p-4">
          <h4 className="mb-3 text-sm font-semibold text-gray-900 dark:text-gray-100">Local Web GUI / NBI Users</h4>
          <div className="mb-4 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Input placeholder="username" value={newUser.username} onChange={(e) => setNewUser((p) => ({ ...p, username: e.target.value }))} />
            <Input type="password" placeholder="password (min 12 chars)" value={newUser.password} onChange={(e) => setNewUser((p) => ({ ...p, password: e.target.value }))} />
            <Select value={newUser.role} onChange={(e) => setNewUser((p) => ({ ...p, role: e.target.value }))}>
              <option value="admin">Admin</option>
              <option value="super_user">Super User</option>
              <option value="config_manager">Config Manager</option>
              <option value="operator">Operator</option>
              <option value="viewer">Viewer</option>
              <option value="nbi_read">NBI Read</option>
              <option value="nbi_write">NBI Write</option>
            </Select>
            <Select value={newUser.user_type} onChange={(e) => setNewUser((p) => ({ ...p, user_type: e.target.value }))}>
              <option value="web">Web GUI</option>
              <option value="nbi">NBI REST API</option>
            </Select>
            <Button onClick={createUser}>Add User</Button>
          </div>
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full text-sm text-gray-700 dark:text-gray-200">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {['Username', 'Type', 'Role', 'Virtual Domain', 'Status'].map((h) => <th key={h} className="px-4 py-2 text-left text-xs uppercase text-gray-500 dark:text-gray-400">{h}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{user.username}</td>
                    <td className="px-4 py-2">{user.user_type === 'nbi' ? 'NBI REST API' : 'Web GUI'}</td>
                    <td className="px-4 py-2">{user.role}</td>
                    <td className="px-4 py-2">{user.virtual_domain || 'All devices'}</td>
                    <td className="px-4 py-2"><Badge variant={user.enabled ? 'success' : 'neutral'}>{user.enabled ? 'Enabled' : 'Disabled'}</Badge></td>
                  </tr>
                ))}
                {users.length === 0 && <tr><td className="px-4 py-4 text-gray-500" colSpan={5}>No local users configured.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </Card>
    </div>
  );
}

function PlaceholderPanel({ title, items }: { title: string; items: string[] }) {
  return (
    <Card>
      <CardHeader title={title} />
      <div className="p-4 text-sm">
        <p className="mb-3 text-gray-500">Configure the following functions (coming soon):</p>
        <ul className="list-disc space-y-1 pl-5 text-gray-700 dark:text-gray-300">
          {items.map((item) => (
            <li key={item}>{item}</li>
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
    case 'mail':
      return (
        <PlaceholderPanel
          title="Mail and Notifications"
          items={[
            'SMTP server (host, port, TLS, auth)',
            'Sender address and reply-to',
            'Notification receivers (email, webhook, syslog)',
            'Per-severity routing rules',
          ]}
        />
      );
    case 'network':
      return (
        <PlaceholderPanel
          title="Network and Devices"
          items={[
            'Default CLI session settings (timeout, retries)',
            'Default SNMP polling parameters',
            'Controller upgrade policies',
            'Plug & Play onboarding',
          ]}
        />
      );
    case 'inventory':
      return (
        <PlaceholderPanel
          title="Inventory"
          items={[
            'Configuration management',
            'Configuration archives',
            'Image management',
            'Device group management',
            'Discovery settings',
          ]}
        />
      );
    case 'alarms':
      return (
        <PlaceholderPanel
          title="Alarms and Events"
          items={[
            'Alarm severity mapping',
            'System events configuration',
            'Trap storage and forwarding',
            'Syslog ingestion (UDP/TCP)',
            'Notification receivers',
          ]}
        />
      );
    case 'clients':
      return <ClientsUsersPanel />;
    case 'services':
      return <PlaceholderPanel title="Services" items={['PTP / SyncE configuration']} />;
  }
}

function Settings() {
  const [active, setActive] = useState<CategoryKey>('general');

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="System Settings"
        subtitle="The product allows an administrator to configure or modify the network and system wide settings."
      />

      <div className="grid grid-cols-12 gap-6">
        <aside className="col-span-12 md:col-span-4 lg:col-span-3 space-y-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              onClick={() => setActive(cat.key)}
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
                  </div>
                  <p className="mt-1 text-xs leading-snug text-gray-600 dark:text-gray-400 line-clamp-3">
                    {cat.description}
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 text-gray-400" />
              </div>
            </button>
          ))}
        </aside>

        <main className="col-span-12 md:col-span-8 lg:col-span-9">
          <CategoryContent category={active} />
        </main>
      </div>
    </div>
  );
}

export default Settings;
