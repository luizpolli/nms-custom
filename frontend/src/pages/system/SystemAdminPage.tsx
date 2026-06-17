import { useState } from 'react';
import { Database, Server } from 'lucide-react';
import { PageHeader } from '../../components/ui';
import { ContainersPanel } from './ContainersPanel';
import { BackupsPanel } from './BackupsPanel';

type Tab = 'containers' | 'backups';

const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'containers', label: 'Services & Containers', icon: <Server className="h-4 w-4" /> },
  { key: 'backups',    label: 'Backup Jobs',           icon: <Database className="h-4 w-4" /> },
];

export function SystemAdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>('containers');

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="System Administration" subtitle="Container status, backup jobs, and system maintenance" />

      {/* Tab bar */}
      <div className="border-b border-gray-200 bg-white px-6 dark:border-gray-700 dark:bg-gray-900">
        <nav className="-mb-px flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={[
                'flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors',
                activeTab === tab.key
                  ? 'border-cisco-blue text-cisco-blue'
                  : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300',
              ].join(' ')}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {activeTab === 'containers' && <ContainersPanel />}
        {activeTab === 'backups'    && <BackupsPanel />}
      </div>
    </div>
  );
}
