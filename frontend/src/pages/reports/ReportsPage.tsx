import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import axios, { type AxiosResponse } from 'axios';
import { ReportCard, type AvailableReport } from './components/ReportCard';
import { ReportParamsForm, type ReportParams } from './components/ReportParamsForm';
import { downloadBlob, extractFilename, formatExtFromFormat } from './lib/download';

const FORMAT_GROUPS: Record<string, string> = {
  excel: 'Excel',
  xlsx: 'Excel',
  pdf: 'PDF',
};

function groupByFormat(reports: AvailableReport[]): Record<string, AvailableReport[]> {
  return reports.reduce<Record<string, AvailableReport[]>>((acc, r) => {
    const group = FORMAT_GROUPS[r.format.toLowerCase()] ?? r.format.toUpperCase();
    if (!acc[group]) acc[group] = [];
    acc[group].push(r);
    return acc;
  }, {});
}

export default function ReportsPage() {
  const [selected, setSelected] = useState<AvailableReport | null>(null);
  const [params, setParams] = useState<ReportParams>({});
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  const { data: reports = [], isLoading } = useQuery<AvailableReport[]>({
    queryKey: ['reports-available'],
    queryFn: async () => {
      const res = await axios.get<AvailableReport[]>('/api/reports/available');
      return res.data;
    },
  });

  const { mutate: generate, isPending } = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error('No report selected');
      const res: AxiosResponse<Blob> = await axios.post(
        '/api/reports/generate',
        { name: selected.name, params },
        { responseType: 'blob' }
      );
      const disposition = res.headers['content-disposition'] as string | null ?? null;
      const ext = formatExtFromFormat(selected.format);
      const filename = extractFilename(disposition, `nms-${selected.name}`, ext);
      downloadBlob(res.data, filename);
    },
    onSuccess: () => showToast('Report generated and downloaded', 'success'),
    onError: (err: Error) => showToast(err.message ?? 'Failed to generate report', 'error'),
  });

  const showToast = (msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const groups = groupByFormat(reports);

  const handleSelect = (r: AvailableReport) => {
    setSelected(r);
    setParams({});
  };

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 rounded-md px-4 py-2 text-sm text-white shadow-lg ${
            toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* Left panel */}
      <aside className="w-72 flex-shrink-0 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-y-auto p-4">
        <h1 className="text-base font-semibold text-gray-900 dark:text-white mb-4">Reports</h1>

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
            Loading...
          </div>
        ) : reports.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">No reports available</p>
        ) : (
          <div className="space-y-5">
            {Object.entries(groups).map(([group, items]) => (
              <div key={group}>
                <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">{group}</p>
                <div className="space-y-2">
                  {items.map((r) => (
                    <ReportCard
                      key={r.name}
                      report={r}
                      selected={selected?.name === r.name}
                      onClick={() => handleSelect(r)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* Right panel */}
      <main className="flex-1 overflow-y-auto p-6">
        {!selected ? (
          <div className="flex h-full items-center justify-center text-gray-500 dark:text-gray-400">
            <div className="text-center">
              <p className="text-lg mb-1">Select a report</p>
              <p className="text-sm">Choose a report from the list to configure and generate</p>
            </div>
          </div>
        ) : (
          <div className="max-w-lg space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{selected.name}</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{selected.description}</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-4">Parameters</h3>
              <ReportParamsForm
                reportName={selected.name}
                params={params}
                onChange={setParams}
              />
            </div>

            <button
              onClick={() => generate()}
              disabled={isPending}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
            >
              {isPending ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Generating...
                </>
              ) : (
                'Generate'
              )}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
