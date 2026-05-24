import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Plus, Eye, Trash2, Upload, Download, Settings2 } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuthStore } from '../../stores/auth';
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
  role?: string;
  lifecycle_state?: string;
  platform_family?: string;
  site_id?: string;
  created_at?: string;
}

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

interface ColumnDef {
  key: string;
  header: string;
  defaultVisible: boolean;
  render?: (value: unknown, row: Device) => React.ReactNode;
}

const STORAGE_KEY = 'nms-device-columns';

function loadVisibleColumns(): Set<string> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return new Set(JSON.parse(stored) as string[]);
  } catch { /* ignore */ }
  return new Set(ALL_COLUMNS.filter((c) => c.defaultVisible).map((c) => c.key));
}

function saveVisibleColumns(keys: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...keys]));
}

const ALL_COLUMNS: ColumnDef[] = [
  { key: 'name', header: 'Name', defaultVisible: true },
  { key: 'ip_address', header: 'IP Address', defaultVisible: true },
  { key: 'device_type', header: 'Device Type', defaultVisible: false },
  {
    key: 'vendor',
    header: 'Vendor',
    defaultVisible: true,
  },
  {
    key: 'model',
    header: 'Model',
    defaultVisible: true,
  },
  {
    key: 'os_type',
    header: 'OS Type',
    defaultVisible: true,
    render: (_: unknown, row: Device) => row.os_type || '—',
  },
  {
    key: 'status',
    header: 'Status',
    defaultVisible: true,
    render: (_: unknown, row: Device) => <DeviceStatusBadge status={row.status} />,
  },
  {
    key: 'role',
    header: 'Role',
    defaultVisible: false,
    render: (_: unknown, row: Device) => row.role || '—',
  },
  {
    key: 'lifecycle_state',
    header: 'Lifecycle',
    defaultVisible: false,
    render: (_: unknown, row: Device) => row.lifecycle_state || '—',
  },
  {
    key: 'platform_family',
    header: 'Platform',
    defaultVisible: false,
    render: (_: unknown, row: Device) => row.platform_family || '—',
  },
  {
    key: 'site_id',
    header: 'Site',
    defaultVisible: false,
    render: (_: unknown, row: Device) => row.site_id || row.location || '—',
  },
  {
    key: 'tags',
    header: 'Tags',
    defaultVisible: true,
    render: (_: unknown, row: Device) => <DeviceTagList tags={row.tags} />,
  },
  {
    key: 'created_at',
    header: 'Created',
    defaultVisible: false,
    render: (_: unknown, row: Device) =>
      row.created_at ? new Date(row.created_at).toLocaleDateString() : '—',
  },
];

// ---------------------------------------------------------------------------
// Column picker popover
// ---------------------------------------------------------------------------

function ColumnPicker({
  visible,
  onChange,
}: {
  visible: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  const [open, setOpen] = useState(false);

  const toggle = (key: string) => {
    const next = new Set(visible);
    if (next.has(key)) {
      if (next.size <= 2) return; // keep at least 2
      next.delete(key);
    } else {
      next.add(key);
    }
    onChange(next);
    saveVisibleColumns(next);
  };

  return (
    <div className="relative">
      <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)} title="Customize columns">
        <Settings2 className="w-4 h-4" />
      </Button>
      {open && (
        <>
          {/* backdrop */}
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-2 w-56 rounded-md border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-900">
            <div className="px-3 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-800">
              Show / Hide Columns
            </div>
            {ALL_COLUMNS.map((col) => (
              <label
                key={col.key}
                className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer dark:text-gray-200 dark:hover:bg-gray-800"
              >
                <input
                  type="checkbox"
                  checked={visible.has(col.key)}
                  onChange={() => toggle(col.key)}
                  className="rounded border-gray-300 dark:border-gray-600"
                />
                {col.header}
              </label>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

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
  const [includeCredentials, setIncludeCredentials] = useState(false);
  const [visibleCols, setVisibleCols] = useState<Set<string>>(loadVisibleColumns);
  const user = useAuthStore((state) => state.user);
  const canExportCredentials = ['root', 'admin'].includes((user?.name || '').toLowerCase());

  const queryKey = ['devices', { search, status, vendor, tag }];

  const { data, isLoading, isError } = useQuery<Device[]>({
    queryKey,
    queryFn: () =>
      api
        .get('/devices', {
          params: {
            q: search || undefined,
            status: status || undefined,
            vendor: vendor || undefined,
            tag: tag || undefined,
            limit: 1000,
          },
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

  const handleDelete = useCallback((device: Device) => {
    if (!window.confirm(`Delete device "${device.name}"?`)) return;
    deleteMutation.mutate(device.id);
  }, [deleteMutation]);

  const openCreate = () => {
    setEditDevice(null);
    setModalOpen(true);
  };

  const openEdit = (device: Device) => {
    setEditDevice(device);
    setModalOpen(true);
  };

  const exportCsv = async () => {
    const response = await api.get('/devices/export', {
      params: { format: 'csv', include_credentials: includeCredentials && canExportCredentials },
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = includeCredentials && canExportCredentials ? 'devices_export_with_credentials.csv' : 'devices_export.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const allDevices = Array.isArray(data) ? data : [];
  const total = allDevices.length;
  const devices = allDevices.slice(offset, offset + LIMIT);
  const pages = Math.max(1, Math.ceil(total / LIMIT));
  const currentPage = Math.floor(offset / LIMIT) + 1;

  // Build columns from visible set + always-on actions column
  const columns = [
    ...ALL_COLUMNS.filter((c) => visibleCols.has(c.key)).map((c) => ({
      key: c.key,
      header: c.header,
      render: c.render,
    })),
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
          <div className="flex flex-wrap items-center gap-2">
            {canExportCredentials && (
              <label className="inline-flex items-center gap-2 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 dark:border-gray-600 dark:text-gray-200">
                <input
                  type="checkbox"
                  checked={includeCredentials}
                  onChange={(e) => setIncludeCredentials(e.target.checked)}
                />
                Credentials
              </label>
            )}
            <Button variant="ghost" onClick={exportCsv}>
              <Download className="w-4 h-4 mr-1" /> Export CSV
            </Button>
            <Button variant="ghost" onClick={() => setImportOpen(true)}>
              <Upload className="w-4 h-4 mr-1" /> Import CSV
            </Button>
            <Button onClick={openCreate}>
              <Plus className="w-4 h-4 mr-1" /> Add Device
            </Button>
          </div>
        }
      />

      {/* Filter bar + column picker */}
      <div className="flex flex-wrap items-center gap-3">
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
        <div className="ml-auto">
          <ColumnPicker visible={visibleCols} onChange={setVisibleCols} />
        </div>
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
