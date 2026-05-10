import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Plus, Eye, Trash2 } from 'lucide-react';
import { api } from '../../lib/api';
import {
  PageHeader,
  Button,
  Input,
  Select,
  Table,
  EmptyState,
  Spinner,
} from '../../components/ui';
import { DeviceStatusBadge } from './components/DeviceStatusBadge';
import { DeviceTagList } from './components/DeviceTagList';
import { PollButton } from './components/PollButton';
import { DeviceFormModal } from './DeviceFormModal';

interface Device {
  id: string;
  name: string;
  ip_address: string;
  vendor: string;
  model: string;
  os_type: string;
  status: string;
  tags: string[];
  device_type: string;
  location: string;
  credential_id: string;
}

interface DevicesResponse {
  items: Device[];
  total: number;
}

const LIMIT = 20;
const VENDOR_OPTIONS = [
  { value: '', label: 'Todos los fabricantes' },
  { value: 'Cisco', label: 'Cisco' },
  { value: 'Juniper', label: 'Juniper' },
  { value: 'Huawei', label: 'Huawei' },
];
const STATUS_OPTIONS = [
  { value: '', label: 'Todos los estados' },
  { value: 'reachable', label: 'Alcanzable' },
  { value: 'unreachable', label: 'No alcanzable' },
  { value: 'unknown', label: 'Desconocido' },
];

export function DevicesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [vendor, setVendor] = useState('');
  const [tag, setTag] = useState('');
  const [offset, setOffset] = useState(0);
  const [modalOpen, setModalOpen] = useState(false);
  const [editDevice, setEditDevice] = useState<Device | null>(null);

  const queryKey = ['devices', { search, status, vendor, tag, offset }];

  const { data, isLoading, isError } = useQuery<DevicesResponse>({
    queryKey,
    queryFn: () =>
      api
        .get('/devices', {
          params: { q: search || undefined, status: status || undefined, vendor: vendor || undefined, tag: tag || undefined, limit: LIMIT, offset },
        })
        .then((r) => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/devices/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
    onError: (err) => {
      console.error('Delete failed', err);
      alert('Error al eliminar el dispositivo');
    },
  });

  const handleDelete = (device: Device) => {
    if (!window.confirm(`¿Eliminar dispositivo "${device.name}"?`)) return;
    deleteMutation.mutate(device.id);
  };

  const openCreate = () => {
    setEditDevice(null);
    setModalOpen(true);
  };

  const openEdit = (device: Device) => {
    setEditDevice(device);
    setModalOpen(true);
  };

  const devices = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = Math.ceil(total / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;

  const columns = [
    { key: 'name', header: 'Nombre' },
    { key: 'ip_address', header: 'IP' },
    {
      key: 'vendor_model',
      header: 'Fabricante / Modelo',
      render: (_: unknown, row: Device) => `${row.vendor || '—'} / ${row.model || '—'}`,
    },
    { key: 'os_type', header: 'OS' },
    {
      key: 'status',
      header: 'Estado',
      render: (_: unknown, row: Device) => <DeviceStatusBadge status={row.status} />,
    },
    {
      key: 'tags',
      header: 'Etiquetas',
      render: (_: unknown, row: Device) => <DeviceTagList tags={row.tags} />,
    },
    {
      key: 'actions',
      header: 'Acciones',
      render: (_: unknown, row: Device) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={() => navigate(`/devices/${row.id}`)} title="Ver">
            <Eye className="w-4 h-4" />
          </Button>
          <PollButton deviceId={row.id} onSuccess={() => queryClient.invalidateQueries({ queryKey: ['devices'] })} />
          <Button variant="ghost" size="sm" onClick={() => openEdit(row)} title="Editar">
            Editar
          </Button>
          <Button variant="ghost" size="sm" onClick={() => handleDelete(row)} title="Eliminar">
            <Trash2 className="w-4 h-4 text-red-500" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Dispositivos"
        subtitle={`${total} dispositivos registrados`}
        actions={
          <Button onClick={openCreate}>
            <Plus className="w-4 h-4 mr-1" /> Crear dispositivo
          </Button>
        }
      />

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Buscar por nombre o IP..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
          className="w-64"
        />
        <Select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setOffset(0); }}
          options={STATUS_OPTIONS}
        />
        <Select
          value={vendor}
          onChange={(e) => { setVendor(e.target.value); setOffset(0); }}
          options={VENDOR_OPTIONS}
        />
        <Input
          placeholder="Filtrar por etiqueta..."
          value={tag}
          onChange={(e) => { setTag(e.target.value); setOffset(0); }}
          className="w-44"
        />
      </div>

      {isLoading && <Spinner />}
      {isError && <p className="text-red-500">Error al cargar dispositivos.</p>}
      {!isLoading && !isError && devices.length === 0 && (
        <EmptyState title="Sin dispositivos" description="Crea el primer dispositivo con el botón superior." />
      )}
      {!isLoading && devices.length > 0 && <Table columns={columns} data={devices} />}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" disabled={offset === 0} onClick={() => setOffset((p) => Math.max(0, p - LIMIT))}>
            Anterior
          </Button>
          <span className="text-sm text-gray-600">
            Página {currentPage} de {pages}
          </span>
          <Button variant="ghost" size="sm" disabled={offset + LIMIT >= total} onClick={() => setOffset((p) => p + LIMIT)}>
            Siguiente
          </Button>
        </div>
      )}

      <DeviceFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        device={editDevice}
      />
    </div>
  );
}
