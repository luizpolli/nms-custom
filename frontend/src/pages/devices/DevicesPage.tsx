import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Plus, Eye, Trash2, Upload } from 'lucide-react';
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
import { ImportCSVModal } from './ImportCSVModal';

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
  { value: '', label: 'All vendors' },
  { value: 'Cisco', label: 'Cisco' },
  { value: 'Juniper', label: 'Juniper' },
  { value: 'Huawei', label: 'Huawei' },
];
const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'reachable', label: 'Reachable' },
  { value: 'unreachable', label: 'Unreachable' },
  { value: 'unknown', label: 'Unknown' },
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
  const [importOpen, setImportOpen] = useState(false);

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
      alert('Failed to delete device');
    },
  });

  const handleDelete = (device: Device) => {
    if (!window.confirm(`Delete device "${device.name}"?`)) return;
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
    { key: 'name', header: 'Name' },
    { key: 'ip_address', header: 'IP' },
    {
      key: 'vendor_model',
      header: 'Vendor / Model',
      render: (_: unknown, row: Device) => `${row.vendor || '—'} / ${row.model || '—'}`,
    },
    { key: 'os_type', header: 'OS' },
    {
      key: 'status',
      header: 'Status',
      render: (_: unknown, row: Device) => <DeviceStatusBadge status={row.status} />,
    },
    {
      key: 'tags',
      header: 'Tags',
      render: (_: unknown, row: Device) => <DeviceTagList tags={row.tags} />,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (_: unknown, row: Device) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={() => navigate(`/devices/${row.id}`)} title="View">
            <Eye className="w-4 h-4" />
          </Button>
          <PollButton deviceId={row.id} onSuccess={() => queryClient.invalidateQueries({ queryKey: ['devices'] })} />
          <Button variant="ghost" size="sm" onClick={() => openEdit(row)} title="Edit">
            Edit
          </Button>
          <Button variant="ghost" size="sm" onClick={() => handleDelete(row)} title="Delete">
            <Trash2 className="w-4 h-4 text-red-500" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Devices"
        subtitle={`${total} registered devices`}
        actions={
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setImportOpen(true)}>
              <Upload className="w-4 h-4 mr-1" /> Import CSV
            </Button>
            <Button onClick={openCreate}>
              <Plus className="w-4 h-4 mr-1" /> Add Device
            </Button>
          </div>
        }
      />

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Search by name or IP..."
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
          placeholder="Filter by tag..."
          value={tag}
          onChange={(e) => { setTag(e.target.value); setOffset(0); }}
          className="w-44"
        />
      </div>

      {isLoading && <Spinner />}
      {isError && <p className="text-red-500">Failed to load devices.</p>}
      {!isLoading && !isError && devices.length === 0 && (
        <EmptyState title="No devices" description="Create the first device using the button above." />
      )}
      {!isLoading && devices.length > 0 && <Table columns={columns} data={devices} />}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" disabled={offset === 0} onClick={() => setOffset((p) => Math.max(0, p - LIMIT))}>
            Previous
          </Button>
          <span className="text-sm text-gray-600">
            Page {currentPage} of {pages}
          </span>
          <Button variant="ghost" size="sm" disabled={offset + LIMIT >= total} onClick={() => setOffset((p) => p + LIMIT)}>
            Next
          </Button>
        </div>
      )}

      <DeviceFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        device={editDevice}
      />

      <ImportCSVModal open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  );
}
