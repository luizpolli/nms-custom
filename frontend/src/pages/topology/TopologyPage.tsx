import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { TopologyGraph, type ApiNode, type ApiLink } from './components/TopologyGraph';
import { RebuildButton } from './components/RebuildButton';

interface TopologyResponse {
  nodes: ApiNode[];
  links: ApiLink[];
}

const LEGEND = [
  { label: 'Cisco', color: 'bg-blue-500' },
  { label: 'Juniper', color: 'bg-green-500' },
  { label: 'Arista', color: 'bg-teal-500' },
  { label: 'Unknown', color: 'bg-gray-400' },
];

export default function TopologyPage() {
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  const { data, isLoading, isError, refetch } = useQuery<TopologyResponse>({
    queryKey: ['topology'],
    queryFn: async () => {
      const res = await axios.get<TopologyResponse>('/api/topology/graph');
      return res.data;
    },
  });

  const showToast = (msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex-shrink-0">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">Network Topology</h1>

        <div className="flex items-center gap-4">
          {/* Legend */}
          <div className="hidden sm:flex items-center gap-3">
            {LEGEND.map((l) => (
              <span key={l.label} className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                <span className={`h-3 w-3 rounded-full ${l.color}`} />
                {l.label}
              </span>
            ))}
          </div>

          <RebuildButton
            onSuccess={() => {
              showToast('Topology rebuilt successfully', 'success');
              refetch();
            }}
            onError={(msg) => showToast(msg, 'error')}
          />
        </div>
      </header>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 rounded-md px-4 py-2 text-sm text-white shadow-lg ${
            toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* Canvas */}
      <div className="flex-1 relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 dark:bg-gray-900/70 z-10">
            <span className="text-sm text-gray-500 dark:text-gray-400">Loading topology...</span>
          </div>
        )}

        {isError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <p className="text-red-500 mb-2">Failed to load topology</p>
              <button
                onClick={() => refetch()}
                className="text-sm text-blue-600 underline"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {!isLoading && !isError && data && data.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-gray-500 dark:text-gray-400">
              <p className="text-lg mb-2">No devices in topology</p>
              <p className="text-sm">Use the "Rebuild all" button to start.</p>
            </div>
          </div>
        )}

        {!isLoading && !isError && data && data.nodes.length > 0 && (
          <TopologyGraph nodes={data.nodes} links={data.links} />
        )}
      </div>
    </div>
  );
}
