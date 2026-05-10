import { useState } from 'react';
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
      return (
        <PlaceholderPanel
          title="Clients and Users"
          items={[
            'Local users and roles',
            'Client troubleshooting',
            'Database settings',
            'Client discovery',
            'OUI database',
          ]}
        />
      );
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
