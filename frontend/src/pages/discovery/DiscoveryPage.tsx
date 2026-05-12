import { useState } from 'react';
import axios from 'axios';
import { ScanForm, type ScanFormValues } from './components/ScanForm';
import { ScanResultsTable, type DiscoveredDevice } from './components/ScanResultsTable';
import { DeviceFormModal } from '../devices/DeviceFormModal';

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
  const [deviceModalOpen, setDeviceModalOpen] = useState(false);
  const [deviceInitialValues, setDeviceInitialValues] = useState<Record<string, unknown> | null>(null);

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
      const msg = err instanceof Error ? err.message : 'Network scan failed';
      setError(msg);
    } finally {
      setIsScanning(false);
    }
  };

  const handleAddDevice = (device: DiscoveredDevice) => {
    setDeviceInitialValues({
      identification: 'ip',
      ip_address: device.ip,
      name: device.sys_name || device.ip,
      vendor: device.vendor || '',
      os_type: device.os_type || 'ios-xr',
      model: '',
      device_type: 'router',
      tags: ['discovered'],
    });
    setDeviceModalOpen(true);
  };

  return (
    <div className="p-6 space-y-6 bg-gray-50 dark:bg-gray-900 min-h-screen">
      {toast && (
        <div className="fixed top-4 right-4 z-50 rounded-md bg-green-600 px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}

      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Network Discovery</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Scan a CIDR range to discover devices via SNMP
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
          Scanning the network, this may take several seconds...
        </div>
      )}

      {summary && !isScanning && (
        <div className="flex gap-4">
          <div className="rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-4 py-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Discovered</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.discovered}</p>
          </div>
          <div className="rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-4 py-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Persisted</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.persisted}</p>
          </div>
        </div>
      )}

      {results !== null && !isScanning && (
        <ScanResultsTable devices={results} onAddDevice={handleAddDevice} />
      )}

      <DeviceFormModal
        open={deviceModalOpen}
        onClose={() => {
          setDeviceModalOpen(false);
          setToast('Discovery device form closed');
          setTimeout(() => setToast(null), 2500);
        }}
        initialValues={deviceInitialValues as never}
      />
    </div>
  );
}
