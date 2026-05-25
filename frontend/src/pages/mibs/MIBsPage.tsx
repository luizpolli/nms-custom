import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { MIBUploadModal } from './components/MIBUploadModal';
import { MIBFormModal, type MIB } from './components/MIBFormModal';

interface MIBRecord extends MIB {
  id: string;
  file_path?: string;
  created_at?: string;
}

function StatusBadge({ status }: { status: string }) {
  const cls = status === 'active'
    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
    : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400';
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status === 'active' ? 'Active' : 'Inactive'}
    </span>
  );
}

export function MIBsPage({ embedded = false }: { embedded?: boolean }) {
  const [showUpload, setShowUpload] = useState(false);
  const [editMib, setEditMib] = useState<MIBRecord | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const qc = useQueryClient();

  const { data: mibs = [], isLoading } = useQuery<MIBRecord[]>({
    queryKey: ['mibs'],
    queryFn: async () => {
      const res = await axios.get<MIBRecord[]>('/api/mibs');
      return res.data;
    },
  });

  const { mutate: deleteMib } = useMutation({
    mutationFn: (id: string) => axios.delete(`/api/mibs/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mibs'] });
      setDeleteId(null);
      showMsg('MIB deleted');
    },
  });

  const showMsg = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <div className={embedded ? 'space-y-6' : 'min-h-screen bg-gray-50 p-6 dark:bg-gray-900'}>
      {toast && (
        <div className="fixed top-4 right-4 z-50 rounded-md bg-green-600 px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            {embedded ? 'MIB catalog / SNMP objects' : 'MIBs'}
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Upload, register, and manage MIB definitions used by SNMP polling, custom KPIs, inventory enrichment, and trap OID context.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setEditMib(null); setShowForm(true); }}
            className="rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            New MIB
          </button>
          <button
            onClick={() => setShowUpload(true)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Upload MIB
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          Loading MIBs...
        </div>
      ) : mibs.length === 0 ? (
        <div className="text-center py-16 text-gray-500 dark:text-gray-400">
          <p className="text-lg mb-1">No registered MIBs</p>
          <p className="text-sm">Upload a .mib file to get started</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                {['Name', 'Root OID', 'Status', 'File path', 'Created', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {mibs.map((mib) => (
                <tr key={mib.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{mib.name}</td>
                  <td className="px-4 py-3 text-sm font-mono text-gray-700 dark:text-gray-300">{mib.oid_root}</td>
                  <td className="px-4 py-3"><StatusBadge status={mib.status} /></td>
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate">{mib.file_path ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                    {mib.created_at ? new Date(mib.created_at).toLocaleDateString('en-US') : '—'}
                  </td>
                  <td className="px-4 py-3 flex items-center gap-3">
                    <button
                      onClick={() => { setEditMib(mib); setShowForm(true); }}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setDeleteId(mib.id)}
                      className="text-xs text-red-500 hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Delete confirm */}
      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-sm w-full">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-2">Confirm deletion</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">This action cannot be undone.</p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteId(null)}
                className="rounded-md border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm text-gray-700 dark:text-gray-300"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMib(deleteId)}
                className="rounded-md bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {showUpload && (
        <MIBUploadModal
          onClose={() => setShowUpload(false)}
          onUploaded={() => { setShowUpload(false); showMsg('MIB uploaded successfully'); }}
        />
      )}

      {showForm && (
        <MIBFormModal
          mib={editMib ?? undefined}
          onClose={() => { setShowForm(false); setEditMib(null); }}
          onSaved={() => { setShowForm(false); setEditMib(null); showMsg('MIB saved'); }}
        />
      )}
    </div>
  );
}

export default MIBsPage;
