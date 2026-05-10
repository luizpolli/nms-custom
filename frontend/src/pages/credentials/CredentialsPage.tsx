import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { api } from '../../lib/api';
import { PageHeader, Button, Badge, Spinner, EmptyState } from '../../components/ui';
import { CredentialFormModal } from './CredentialFormModal';

interface Credential {
  id: string;
  name: string;
  hostname: string;
  username: string;
  protocol: string;
  snmp_version: string;
  port: number;
  has_secret: boolean;
}

export function CredentialsPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editCred, setEditCred] = useState<Credential | null>(null);

  const { data, isLoading, isError } = useQuery<Credential[]>({
    queryKey: ['credentials'],
    queryFn: () => api.get('/credentials').then((r) => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/credentials/${id}`),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['credentials'] });
      const prev = queryClient.getQueryData<Credential[]>(['credentials']);
      queryClient.setQueryData<Credential[]>(['credentials'], (old) => old?.filter((c) => c.id !== id) ?? []);
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      queryClient.setQueryData(['credentials'], ctx?.prev);
      alert('Failed to delete credential');
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['credentials'] }),
  });

  const openCreate = () => { setEditCred(null); setModalOpen(true); };
  const openEdit = (cred: Credential) => { setEditCred(cred); setModalOpen(true); };

  const credentials = data ?? [];

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Credentials"
        subtitle={`${credentials.length} credential profiles`}
        actions={
          <Button onClick={openCreate}>
            <Plus className="w-4 h-4 mr-1" /> Add Credential Profile
          </Button>
        }
      />

      {isLoading && <Spinner />}
      {isError && <p className="text-red-500">Failed to load credentials.</p>}
      {!isLoading && credentials.length === 0 && (
        <EmptyState title="No credentials" description="Create the first credential using the button above." />
      )}

      {credentials.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['Name', 'Hostname', 'Username', 'Protocol', 'SNMP', 'Port', 'Secret', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {credentials.map((cred) => (
                <tr key={cred.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{cred.name}</td>
                  <td className="px-4 py-2">{cred.hostname || '—'}</td>
                  <td className="px-4 py-2">{cred.username || '—'}</td>
                  <td className="px-4 py-2">
                    <Badge variant="default">{cred.protocol.toUpperCase()}</Badge>
                  </td>
                  <td className="px-4 py-2">{cred.snmp_version || '—'}</td>
                  <td className="px-4 py-2">{cred.port}</td>
                  <td className="px-4 py-2">
                    <Badge variant={cred.has_secret ? 'success' : 'warning'}>
                      {cred.has_secret ? 'Yes' : 'No'}
                    </Badge>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(cred)}>Edit</Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (window.confirm(`Delete credential "${cred.name}"?`)) {
                            deleteMutation.mutate(cred.id);
                          }
                        }}
                      >
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CredentialFormModal open={modalOpen} onClose={() => setModalOpen(false)} credential={editCred} />
    </div>
  );
}
