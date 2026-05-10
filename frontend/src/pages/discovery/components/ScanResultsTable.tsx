import React from 'react';

export interface DiscoveredDevice {
  ip: string;
  sys_name: string;
  sys_descr: string;
  vendor: string;
  os_type: string;
}

interface Props {
  devices: DiscoveredDevice[];
  onAddDevice: (device: DiscoveredDevice) => void;
}

function truncate(str: string, max = 60): string {
  return str.length > max ? str.slice(0, max) + '…' : str;
}

export function ScanResultsTable({ devices, onAddDevice }: Props) {
  if (devices.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
        <p className="text-gray-500 dark:text-gray-400">No se encontraron dispositivos</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
          Resultados — {devices.length} dispositivo{devices.length !== 1 ? 's' : ''} encontrado{devices.length !== 1 ? 's' : ''}
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              {['IP', 'Nombre', 'Descripción', 'Vendor', 'OS', 'Acción'].map((h) => (
                <th
                  key={h}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {devices.map((dev) => (
              <tr key={dev.ip} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                <td className="px-4 py-2 text-sm font-mono text-gray-900 dark:text-gray-100">{dev.ip}</td>
                <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">{dev.sys_name || '—'}</td>
                <td className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 max-w-xs" title={dev.sys_descr}>
                  {truncate(dev.sys_descr)}
                </td>
                <td className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300">{dev.vendor || '—'}</td>
                <td className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300">{dev.os_type || '—'}</td>
                <td className="px-4 py-2">
                  <button
                    onClick={() => onAddDevice(dev)}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
                  >
                    Agregar como dispositivo
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
