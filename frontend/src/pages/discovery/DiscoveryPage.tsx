import React, { useState } from 'react';
import axios from 'axios';
import { ScanForm, type ScanFormValues } from './components/ScanForm';
import { ScanResultsTable, type DiscoveredDevice } from './components/ScanResultsTable';

interface ScanResponse {
  discovered: number;
  persisted: number;
  devices: DiscoveredDevice[];
}

interface ScanSummary {
  discovered: number;
  persisted: number;
}

export default function DiscoveryPage() {
  const [isScanning, setIsScanning] = useState(false);
  const [results, setResults] = useState<DiscoveredDevice[] | null>(null);
  const [summary, setSummary] = useState<ScanSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const handleScan = async (values: ScanFormValues) => {
    setIsScanning(true);
    setError(null);
    try {
      const res = await axios.post<ScanResponse>('/api/discovery/scan', {
        cidr: values.cidr,
        communities: values.communities,
      });
      setResults(res.data.devices);
      setSummary({ discovered: res.data.discovered, persisted: res.data.persisted });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al escanear la red';
      setError(msg);
    } finally {
      setIsScanning(false);
    }
  };

  const handleAddDevice = (device: DiscoveredDevice) => {
    setToast(`Dispositivo ${device.ip} agregado (integración pendiente con DeviceFormModal)`);
    setTimeout(() => setToast(null), 3500);
  };

  return (
    <div className="p-6 space-y-6 bg-gray-50 dark:bg-gray-900 min-h-screen">
      {toast && (
        <div className="fixed top-4 right-4 z-50 rounded-md bg-green-600 px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}

      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Descubrimiento de red</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Escanea un rango CIDR para descubrir dispositivos vía SNMP
        </p>
      </div>

      <ScanForm onSubmit={handleScan} isLoading={isScanning} />

      {error && (
        <div className="rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 px-4 py-3">
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      {isScanning && (
        <div className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          Escaneando la red, esto puede tomar varios segundos...
        </div>
      )}

      {summary && !isScanning && (
        <div className="flex gap-4">
          <div className="rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-4 py-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Descubiertos</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.discovered}</p>
          </div>
          <div className="rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-4 py-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Persistidos</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.persisted}</p>
          </div>
        </div>
      )}

      {results !== null && !isScanning && (
        <ScanResultsTable devices={results} onAddDevice={handleAddDevice} />
      )}
    </div>
  );
}
