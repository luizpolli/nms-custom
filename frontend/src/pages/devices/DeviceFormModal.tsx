import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Modal, Button, Input, Select } from '../../components/ui';

interface Credential {
  id: string;
  name: string;
}

interface DeviceFormData {
  name: string;
  ip_address: string;
  device_type: string;
  vendor: string;
  model: string;
  os_type: string;
  location: string;
  tags: string[];
  credential_id: string;
}

interface Device extends DeviceFormData {
  id: string;
  status: string;
}

interface DeviceFormModalProps {
  open: boolean;
  onClose: () => void;
  device?: Device | null;
}

const DEVICE_TYPES = ['router', 'switch', 'firewall', 'server'];
const OS_TYPES = ['ios-xr', 'ios-xe', 'nx-os', 'junos'];

const EMPTY_FORM: DeviceFormData = {
  name: '',
  ip_address: '',
  device_type: 'router',
  vendor: '',
  model: '',
  os_type: 'ios-xr',
  location: '',
  tags: [],
  credential_id: '',
};

export function DeviceFormModal({ open, onClose, device }: DeviceFormModalProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<DeviceFormData>(EMPTY_FORM);
  const [tagsInput, setTagsInput] = useState('');

  const { data: credentials = [] } = useQuery<Credential[]>({
    queryKey: ['credentials'],
    queryFn: () => api.get('/credentials').then((r) => r.data),
    enabled: open,
  });

  useEffect(() => {
    if (device) {
      setForm({
        name: device.name,
        ip_address: device.ip_address,
        device_type: device.device_type,
        vendor: device.vendor,
        model: device.model,
        os_type: device.os_type,
        location: device.location,
        tags: device.tags ?? [],
        credential_id: device.credential_id ?? '',
      });
      setTagsInput((device.tags ?? []).join(', '));
    } else {
      setForm(EMPTY_FORM);
      setTagsInput('');
    }
  }, [device, open]);

  const mutation = useMutation({
    mutationFn: (data: DeviceFormData) =>
      device
        ? api.patch(`/devices/${device.id}`, data)
        : api.post('/devices', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      onClose();
    },
    onError: (err) => {
      console.error('Save device failed', err);
      alert('Error al guardar el dispositivo');
    },
  });

  const handleSet = <K extends keyof DeviceFormData>(key: K, value: DeviceFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleTagsBlur = () => {
    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
    handleSet('tags', tags);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  return (
    <Modal open={open} onClose={onClose} title={device ? 'Editar dispositivo' : 'Crear dispositivo'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Nombre"
          value={form.name}
          onChange={(e) => handleSet('name', e.target.value)}
          required
        />
        <Input
          label="Dirección IP"
          value={form.ip_address}
          onChange={(e) => handleSet('ip_address', e.target.value)}
          placeholder="192.168.1.1"
          required
        />
        <Select
          label="Tipo de dispositivo"
          value={form.device_type}
          onChange={(e) => handleSet('device_type', e.target.value)}
          options={DEVICE_TYPES.map((t) => ({ value: t, label: t }))}
        />
        <Input
          label="Fabricante"
          value={form.vendor}
          onChange={(e) => handleSet('vendor', e.target.value)}
        />
        <Input
          label="Modelo"
          value={form.model}
          onChange={(e) => handleSet('model', e.target.value)}
        />
        <Select
          label="Tipo de OS"
          value={form.os_type}
          onChange={(e) => handleSet('os_type', e.target.value)}
          options={OS_TYPES.map((o) => ({ value: o, label: o }))}
        />
        <Input
          label="Ubicación"
          value={form.location}
          onChange={(e) => handleSet('location', e.target.value)}
        />
        <Input
          label="Etiquetas (separadas por coma)"
          value={tagsInput}
          onChange={(e) => setTagsInput(e.target.value)}
          onBlur={handleTagsBlur}
          placeholder="core, backbone, mx"
        />
        <Select
          label="Credencial"
          value={form.credential_id}
          onChange={(e) => handleSet('credential_id', e.target.value)}
          options={[
            { value: '', label: '— Sin credencial —' },
            ...credentials.map((c) => ({ value: c.id, label: c.name })),
          ]}
        />
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Guardando...' : 'Guardar'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
