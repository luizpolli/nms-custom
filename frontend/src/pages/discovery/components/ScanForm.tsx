import React, { useState } from 'react';
import { clsx } from 'clsx';

const CIDR_REGEX = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,2}$/;

export interface ScanFormValues {
  cidr: string;
  communities: string[];
}

interface Props {
  onSubmit: (values: ScanFormValues) => void;
  isLoading: boolean;
}

export function ScanForm({ onSubmit, isLoading }: Props) {
  const [cidr, setCidr] = useState('');
  const [communitiesRaw, setCommunitiesRaw] = useState('public');
  const [cidrError, setCidrError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!CIDR_REGEX.test(cidr)) {
      setCidrError('Formato CIDR inválido (ej. 192.168.1.0/24)');
      return;
    }
    setCidrError('');
    const communities = communitiesRaw
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean);
    onSubmit({ cidr, communities: communities.length ? communities : ['public'] });
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
      <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-4">Parámetros de escaneo</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Red CIDR <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={cidr}
            onChange={(e) => setCidr(e.target.value)}
            placeholder="192.168.1.0/24"
            className={clsx(
              'w-full rounded-md border px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500',
              cidrError ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'
            )}
          />
          {cidrError && <p className="mt-1 text-xs text-red-500">{cidrError}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Comunidades SNMP
          </label>
          <input
            type="text"
            value={communitiesRaw}
            onChange={(e) => setCommunitiesRaw(e.target.value)}
            placeholder="public, private"
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Separadas por coma</p>
        </div>
      </div>

      <div className="mt-4">
        <button
          type="submit"
          disabled={isLoading}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
        >
          {isLoading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Escaneando...
            </>
          ) : (
            'Iniciar escaneo'
          )}
        </button>
      </div>
    </form>
  );
}
