import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Modal, Button, Input, Select } from '../../components/ui';

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

interface CredentialFormData {
  name: string;
  hostname: string;
  username: string;
  secret: string;
  protocol: string;
  snmp_version: string;
  port: number | '';
}

interface CredentialFormModalProps {
  open: boolean;
  onClose: () => void;
  credential?: Credential | null;
}

const PROTOCOL_OPTIONS = [
  { value: 'ssh', label: 'SSH' },
  { value: 'snmp', label: 'SNMP' },
];
const SNMP_VERSION_OPTIONS = [
  { value: 'v1', label: 'v1' },
  { value: 'v2c', label: 'v2c' },
  { value: 'v3', label: 'v3' },
];

const EMPTY_FORM: CredentialFormData = {
  name: '',
  hostname: '',
  username: '',
  secret: '',
  protocol: 'ssh',
  snmp_version: 'v2c',
  port: 22,
};

export function CredentialFormModal({ open, onClose, credential }: CredentialFormModalProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CredentialFormData>(EMPTY_FORM);

  useEffect(() => {
    if (credential) {
      setForm({
        name: credential.name,
        hostname: credential.hostname,
        username: credential.username,
        secret: '',
        protocol: credential.protocol,
        snmp_version: credential.snmp_version,
        port: credential.port,
      });
    } else {
      setForm(EMPTY_FORM);
    }
  }, [credential, open]);

  const mutation = useMutation({
    mutationFn: (data: Partial<CredentialFormData>) => {
      // On edit, only include secret if filled
      if (credential) {
        const payload = { ...data };
        if (!payload.secret) delete payload.secret;
        return api.patch(`/credentials/${credential.id}`, payload);
      }
      return api.post('/credentials', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
      onClose();
    },
    onError: (err) => {
      console.error('Save credential failed', err);
      alert('Error al guardar la credencial');
    },
  });

  const handleSet = <K extends keyof CredentialFormData>(key: K, value: CredentialFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  return (
    <Modal open={open} onClose={onClose} title={credential ? 'Editar credencial' : 'Crear credencial'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Nombre" value={form.name} onChange={(e) => handleSet('name', e.target.value)} required />
        <Input label="Hostname" value={form.hostname} onChange={(e) => handleSet('hostname', e.target.value)} />
        <Input label="Usuario" value={form.username} onChange={(e) => handleSet('username', e.target.value)} />
        <Input
          label={credential ? 'Contraseña / Secret (dejar vacío para mantener)' : 'Contraseña / Secret'}
          type="password"
          value={form.secret}
          onChange={(e) => handleSet('secret', e.target.value)}
          required={!credential}
        />
        <Select
          label="Protocolo"
          value={form.protocol}
          onChange={(e) => handleSet('protocol', e.target.value)}
          options={PROTOCOL_OPTIONS}
        />
        <Select
          label="Versión SNMP"
          value={form.snmp_version}
          onChange={(e) => handleSet('snmp_version', e.target.value)}
          options={SNMP_VERSION_OPTIONS}
        />
        <Input
          label="Puerto"
          type="number"
          value={form.port === '' ? '' : String(form.port)}
          onChange={(e) => handleSet('port', e.target.value === '' ? '' : Number(e.target.value))}
        />
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Guardando...' : 'Guardar'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
