import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, Layers3, Plus, Trash2, Waypoints } from 'lucide-react';
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, StatCard } from '../../components/ui';
import { api } from '../../lib/api';

type ServiceDependency = {
  id: string;
  source_service_id: string;
  target_service_id: string;
  source_service_name?: string | null;
  target_service_name?: string | null;
  dependency_type: string;
  direction: string;
  weight: number;
  is_critical: boolean;
  description?: string | null;
  created_at: string;
};

type ServiceMember = {
  id: string;
  device_id?: string | null;
  interface_id?: string | null;
  role: string;
  weight: number;
};

type ServiceRecord = {
  id: string;
  name: string;
  kind: string;
  description?: string | null;
  member_count: number;
  created_at: string;
  updated_at: string;
  members: ServiceMember[];
  dependencies: ServiceDependency[];
};

type ServiceImpactMember = {
  member_id: string;
  device_id?: string | null;
  interface_id?: string | null;
  label: string;
  role: string;
  weight: number;
  score: number;
  active_alarms: number;
  worst_severity: string;
};

type ServiceDependencyImpact = {
  dependency_id: string;
  target_service_id: string;
  target_service_name: string;
  target_score: number;
  propagated_penalty: number;
  weight: number;
  is_critical: boolean;
  direction: string;
};

type ServiceImpact = {
  service_id: string;
  name: string;
  kind: string;
  description?: string | null;
  score: number;
  base_score?: number | null;
  dependency_penalty: number;
  health_state: string;
  member_count: number;
  impacted_member_count: number;
  active_alarm_count: number;
  worst_severity: string;
  members: ServiceImpactMember[];
  dependency_impacts: ServiceDependencyImpact[];
};

type DeviceOption = {
  id: string;
  name: string;
  ip_address: string;
  status?: string;
};

type ManagedInterface = {
  id: string;
  device_id: string;
  if_index?: number | null;
  name: string;
  description?: string | null;
  alias?: string | null;
  oper_status?: string | null;
};

type MemberMode = 'device' | 'interface';

type ServiceForm = {
  name: string;
  kind: string;
  description: string;
  member_mode: MemberMode;
  device_id: string;
  interface_id: string;
  role: string;
  weight: string;
};

const EMPTY_FORM: ServiceForm = {
  name: '',
  kind: 'customer',
  description: '',
  member_mode: 'device',
  device_id: '',
  interface_id: '',
  role: 'member',
  weight: '1',
};

const KIND_OPTIONS = [
  { value: 'customer', label: 'Customer' },
  { value: 'transport', label: 'Transport' },
  { value: 'platform', label: 'Platform' },
  { value: 'infrastructure', label: 'Infrastructure' },
  { value: 'other', label: 'Other' },
];

export function ServicesPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [memberService, setMemberService] = useState<ServiceRecord | null>(null);
  const [dependencyService, setDependencyService] = useState<ServiceRecord | null>(null);
  const [form, setForm] = useState<ServiceForm>(EMPTY_FORM);
  const [memberForm, setMemberForm] = useState<{ member_mode: MemberMode; device_id: string; interface_id: string; role: string; weight: string }>({ member_mode: 'device', device_id: '', interface_id: '', role: 'member', weight: '1' });
  const [dependencyForm, setDependencyForm] = useState({ target_service_id: '', dependency_type: 'depends_on', direction: 'source_to_target', weight: '1', is_critical: false, description: '' });

  const servicesQuery = useQuery({
    queryKey: ['services'],
    queryFn: () => api.get<ServiceRecord[]>('/services').then((r) => r.data),
    refetchInterval: 60_000,
  });
  const impactQuery = useQuery({
    queryKey: ['assurance-services', 'full'],
    queryFn: () => api.get<ServiceImpact[]>('/assurance/services', { params: { limit: 100 } }).then((r) => r.data),
    refetchInterval: 60_000,
  });
  const devicesQuery = useQuery({
    queryKey: ['devices', 'service-options'],
    queryFn: () => api.get<DeviceOption[]>('/devices', { params: { limit: 1000 } }).then((r) => r.data),
  });
  const createInterfacesQuery = useQuery({
    queryKey: ['managed-interfaces', form.device_id],
    queryFn: () => api.get<ManagedInterface[]>(`/devices/${form.device_id}/managed-interfaces`).then((r) => r.data),
    enabled: createOpen && form.member_mode === 'interface' && Boolean(form.device_id),
  });
  const memberInterfacesQuery = useQuery({
    queryKey: ['managed-interfaces', memberForm.device_id],
    queryFn: () => api.get<ManagedInterface[]>(`/devices/${memberForm.device_id}/managed-interfaces`).then((r) => r.data),
    enabled: Boolean(memberService) && memberForm.member_mode === 'interface' && Boolean(memberForm.device_id),
  });

  const invalidateServices = () => {
    queryClient.invalidateQueries({ queryKey: ['services'] });
    queryClient.invalidateQueries({ queryKey: ['assurance-services'] });
  };

  const createMutation = useMutation({
    mutationFn: (body: ServiceForm) => {
      const memberPayload = body.member_mode === 'interface'
        ? (body.interface_id ? { interface_id: body.interface_id, role: body.role || 'member', weight: Number(body.weight) || 1 } : null)
        : (body.device_id ? { device_id: body.device_id, role: body.role || 'member', weight: Number(body.weight) || 1 } : null);
      const members = memberPayload ? [memberPayload] : [];
      return api.post('/services', {
        name: body.name,
        kind: body.kind,
        description: body.description || null,
        members,
      });
    },
    onSuccess: () => {
      invalidateServices();
      setCreateOpen(false);
      setForm(EMPTY_FORM);
    },
    onError: (err) => {
      console.error('Create service failed', err);
      alert('Failed to create service');
    },
  });

  const addMemberMutation = useMutation({
    mutationFn: () => {
      if (!memberService) throw new Error('No service selected');
      return api.post(`/services/${memberService.id}/members`, {
        ...(memberForm.member_mode === 'interface' ? { interface_id: memberForm.interface_id } : { device_id: memberForm.device_id }),
        role: memberForm.role || 'member',
        weight: Number(memberForm.weight) || 1,
      });
    },
    onSuccess: () => {
      invalidateServices();
      setMemberService(null);
      setMemberForm({ member_mode: 'device', device_id: '', interface_id: '', role: 'member', weight: '1' });
    },
    onError: (err) => {
      console.error('Add member failed', err);
      alert('Failed to add service member');
    },
  });

  const addDependencyMutation = useMutation({
    mutationFn: () => {
      if (!dependencyService) throw new Error('No service selected');
      return api.post(`/services/${dependencyService.id}/dependencies`, {
        target_service_id: dependencyForm.target_service_id,
        dependency_type: dependencyForm.dependency_type || 'depends_on',
        direction: dependencyForm.direction || 'source_to_target',
        weight: Number(dependencyForm.weight) || 1,
        is_critical: dependencyForm.is_critical,
        description: dependencyForm.description || null,
      });
    },
    onSuccess: () => {
      invalidateServices();
      setDependencyService(null);
      setDependencyForm({ target_service_id: '', dependency_type: 'depends_on', direction: 'source_to_target', weight: '1', is_critical: false, description: '' });
    },
    onError: (err) => {
      console.error('Add dependency failed', err);
      alert('Failed to add service dependency');
    },
  });

  const removeDependencyMutation = useMutation({
    mutationFn: ({ serviceId, dependencyId }: { serviceId: string; dependencyId: string }) => api.delete(`/services/${serviceId}/dependencies/${dependencyId}`),
    onSuccess: invalidateServices,
    onError: (err) => {
      console.error('Remove dependency failed', err);
      alert('Failed to remove dependency');
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ serviceId, memberId }: { serviceId: string; memberId: string }) => api.delete(`/services/${serviceId}/members/${memberId}`),
    onSuccess: invalidateServices,
    onError: (err) => {
      console.error('Remove member failed', err);
      alert('Failed to remove member');
    },
  });

  const deleteServiceMutation = useMutation({
    mutationFn: (serviceId: string) => api.delete(`/services/${serviceId}`),
    onSuccess: invalidateServices,
    onError: (err) => {
      console.error('Delete service failed', err);
      alert('Failed to delete service');
    },
  });

  const impactById = useMemo(() => new Map((impactQuery.data ?? []).map((item) => [item.service_id, item])), [impactQuery.data]);
  const deviceById = useMemo(() => new Map((devicesQuery.data ?? []).map((device) => [device.id, device])), [devicesQuery.data]);
  const deviceOptions = [{ value: '', label: 'No initial member' }, ...(devicesQuery.data ?? []).map((device) => ({ value: device.id, label: `${device.name} (${device.ip_address})` }))];
  const requiredDeviceOptions = [{ value: '', label: 'Select device…' }, ...(devicesQuery.data ?? []).map((device) => ({ value: device.id, label: `${device.name} (${device.ip_address})` }))];
  const createInterfaceOptions = [{ value: '', label: createInterfacesQuery.isFetching ? 'Loading interfaces…' : 'Select interface…' }, ...(createInterfacesQuery.data ?? []).map((iface) => ({ value: iface.id, label: interfaceLabel(iface) }))];
  const memberInterfaceOptions = [{ value: '', label: memberInterfacesQuery.isFetching ? 'Loading interfaces…' : 'Select interface…' }, ...(memberInterfacesQuery.data ?? []).map((iface) => ({ value: iface.id, label: interfaceLabel(iface) }))];
  const services = servicesQuery.data ?? [];
  const dependencyTargetOptions = [{ value: '', label: 'Select target service…' }, ...services.filter((svc) => svc.id !== dependencyService?.id).map((svc) => ({ value: svc.id, label: `${svc.name} (${svc.kind})` }))];
  const impactedCount = (impactQuery.data ?? []).filter((svc) => svc.impacted_member_count > 0 || svc.score < 100).length;
  const averageScore = impactQuery.data?.length
    ? Math.round(impactQuery.data.reduce((sum, svc) => sum + svc.score, 0) / impactQuery.data.length)
    : 100;

  const handleDeleteService = (service: ServiceRecord) => {
    if (!window.confirm(`Delete service "${service.name}"?`)) return;
    deleteServiceMutation.mutate(service.id);
  };

  const handleRemoveMember = (serviceId: string, member: ServiceMember) => {
    if (!window.confirm('Remove this service member?')) return;
    removeMemberMutation.mutate({ serviceId, memberId: member.id });
  };

  const handleRemoveDependency = (serviceId: string, dependency: ServiceDependency) => {
    if (!window.confirm('Remove this service dependency?')) return;
    removeDependencyMutation.mutate({ serviceId, dependencyId: dependency.id });
  };

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Services"
        subtitle="Logical service inventory with live assurance impact from member alarms and interface health"
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> Create service
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <StatCard title="Services modeled" value={services.length} icon={<Layers3 className="h-5 w-5" />} loading={servicesQuery.isLoading} />
        <StatCard title="Average score" value={impactQuery.isLoading ? '—' : averageScore} icon={<Activity className="h-5 w-5" />} tone={averageScore >= 90 ? 'success' : averageScore >= 75 ? 'warning' : 'danger'} loading={impactQuery.isLoading} />
        <StatCard title="Impacted services" value={impactedCount} icon={<Waypoints className="h-5 w-5" />} tone={impactedCount ? 'warning' : 'success'} loading={impactQuery.isLoading} />
      </div>

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Service impact matrix</h2>
          {(servicesQuery.isFetching || impactQuery.isFetching) && <Spinner size="sm" />}
        </div>

        {!services.length ? (
          <EmptyState title="No services modeled" description="Create a service here to group devices and calculate customer, transport, or platform impact." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <Th>Service</Th>
                  <Th>Score</Th>
                  <Th>Worst</Th>
                  <Th>Members</Th>
                  <Th>Impact</Th>
                  <Th>Updated</Th>
                  <Th>Actions</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {services.map((service) => {
                  const impact = impactById.get(service.id);
                  const score = impact?.score ?? 100;
                  return (
                    <tr key={service.id}>
                      <Td>
                        <div className="font-medium text-gray-900 dark:text-white">{service.name}</div>
                        <div className="text-xs text-gray-500">{service.kind}{service.description ? ` · ${service.description}` : ''}</div>
                      </Td>
                      <Td><Badge variant={score >= 90 ? 'success' : score >= 75 ? 'warning' : 'danger'}>{score}</Badge></Td>
                      <Td><Badge variant={(impact?.worst_severity ?? 'info') as never}>{impact?.worst_severity ?? 'info'}</Badge></Td>
                      <Td>{service.member_count}</Td>
                      <Td>{impact ? `${impact.impacted_member_count} members · ${impact.active_alarm_count} alarms${impact.dependency_penalty ? ` · dep -${impact.dependency_penalty}` : ''}` : 'pending score'}</Td>
                      <Td>{new Date(service.updated_at).toLocaleString()}</Td>
                      <Td>
                        <div className="flex gap-2">
                          <Button variant="ghost" size="sm" onClick={() => setMemberService(service)}>Add member</Button>
                          <Button variant="ghost" size="sm" onClick={() => setDependencyService(service)}>Add dependency</Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteService(service)} title="Delete service">
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {services.map((service) => {
          const impact = impactById.get(service.id);
          const score = impact?.score ?? 100;
          const impactMembers = new Map((impact?.members ?? []).map((m) => [m.member_id, m]));
          return (
            <Card key={service.id} className="p-4">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">{service.name}</h3>
                  <p className="text-xs text-gray-500">{service.kind} · {impact?.health_state ?? 'pending'}{impact?.dependency_penalty ? ` · dependency penalty -${impact.dependency_penalty}` : ''}</p>
                </div>
                <Badge variant={score >= 90 ? 'success' : score >= 75 ? 'warning' : 'danger'}>{score}</Badge>
              </div>
              {!!impact?.dependency_impacts?.length && (
                <div className="mb-3 space-y-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-red-500">Propagated dependency impact</div>
                  {impact.dependency_impacts.map((dependency) => (
                    <div key={dependency.dependency_id} className="flex items-center justify-between gap-3 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm dark:border-red-900/40 dark:bg-red-950/20">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-gray-900 dark:text-white">{dependency.target_service_name}</div>
                        <div className="text-xs text-gray-500">target score {dependency.target_score} · penalty -{dependency.propagated_penalty}{dependency.is_critical ? ' · critical' : ''}</div>
                      </div>
                      <Badge variant={dependency.target_score >= 90 ? 'success' : dependency.target_score >= 75 ? 'warning' : 'danger'}>{dependency.target_score}</Badge>
                    </div>
                  ))}
                </div>
              )}
              {!!service.dependencies?.length && (
                <div className="mb-3 space-y-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Dependencies</div>
                  {service.dependencies.map((dependency) => (
                    <div key={dependency.id} className="flex items-center justify-between gap-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm dark:border-blue-900/40 dark:bg-blue-950/20">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-gray-900 dark:text-white">→ {dependency.target_service_name ?? dependency.target_service_id}</div>
                        <div className="text-xs text-gray-500">{dependency.dependency_type} · weight {dependency.weight}{dependency.is_critical ? ' · critical' : ''}</div>
                      </div>
                      <Button variant="ghost" size="xs" onClick={() => handleRemoveDependency(service.id, dependency)} title="Remove dependency">
                        <Trash2 className="h-3.5 w-3.5 text-red-500" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              {!service.members.length ? (
                <EmptyState title="No members" description="Add devices to include this service in impact scoring." />
              ) : (
                <div className="space-y-2">
                  {service.members.slice(0, 8).map((member) => {
                    const impacted = impactMembers.get(member.id);
                    const device = member.device_id ? deviceById.get(member.device_id) : undefined;
                    const memberScore = impacted?.score ?? 100;
                    return (
                      <div key={member.id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-700">
                        <div className="min-w-0">
                          <div className="truncate font-medium text-gray-900 dark:text-white">{impacted?.label ?? device?.name ?? member.device_id ?? member.interface_id ?? member.id}</div>
                          <div className="text-xs text-gray-500">{member.role} · weight {member.weight}</div>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <Badge variant={(impacted?.worst_severity || 'info') as never}>{impacted?.worst_severity ?? 'info'}</Badge>
                          <Badge variant={memberScore >= 90 ? 'success' : memberScore >= 75 ? 'warning' : 'danger'}>{memberScore}</Badge>
                          <Button variant="ghost" size="xs" onClick={() => handleRemoveMember(service.id, member)} title="Remove member">
                            <Trash2 className="h-3.5 w-3.5 text-red-500" />
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create service" size="lg">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); createMutation.mutate(form); }}>
          <Input label="Name" required value={form.name} onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))} />
          <Select label="Kind" options={KIND_OPTIONS} value={form.kind} onChange={(e) => setForm((prev) => ({ ...prev, kind: e.target.value }))} />
          <Input label="Description" value={form.description} onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))} />
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Select label="Initial member type" options={[{ value: 'device', label: 'Device' }, { value: 'interface', label: 'Interface' }]} value={form.member_mode} onChange={(e) => setForm((prev) => ({ ...prev, member_mode: e.target.value as MemberMode, interface_id: '' }))} />
            <Select label="Device" options={deviceOptions} value={form.device_id} onChange={(e) => setForm((prev) => ({ ...prev, device_id: e.target.value, interface_id: '' }))} />
            {form.member_mode === 'interface' && <Select label="Interface" options={createInterfaceOptions} value={form.interface_id} onChange={(e) => setForm((prev) => ({ ...prev, interface_id: e.target.value }))} />}
            <Input label="Role" value={form.role} onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))} />
            <Input label="Weight" type="number" min="0.1" step="0.1" value={form.weight} onChange={(e) => setForm((prev) => ({ ...prev, weight: e.target.value }))} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button type="submit" loading={createMutation.isPending} disabled={!form.name.trim()}>Create</Button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(dependencyService)} onClose={() => setDependencyService(null)} title={`Add dependency${dependencyService ? ` from ${dependencyService.name}` : ''}`} size="lg">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); addDependencyMutation.mutate(); }}>
          <Select label="Target service" required options={dependencyTargetOptions} value={dependencyForm.target_service_id} onChange={(e) => setDependencyForm((prev) => ({ ...prev, target_service_id: e.target.value }))} />
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Input label="Type" value={dependencyForm.dependency_type} onChange={(e) => setDependencyForm((prev) => ({ ...prev, dependency_type: e.target.value }))} />
            <Select label="Direction" options={[{ value: 'source_to_target', label: 'Source → target' }, { value: 'target_to_source', label: 'Target → source' }, { value: 'bidirectional', label: 'Bidirectional' }]} value={dependencyForm.direction} onChange={(e) => setDependencyForm((prev) => ({ ...prev, direction: e.target.value }))} />
            <Input label="Weight" type="number" min="0.1" step="0.1" value={dependencyForm.weight} onChange={(e) => setDependencyForm((prev) => ({ ...prev, weight: e.target.value }))} />
            <label className="flex items-center gap-2 pt-6 text-sm text-gray-700 dark:text-gray-300">
              <input type="checkbox" checked={dependencyForm.is_critical} onChange={(e) => setDependencyForm((prev) => ({ ...prev, is_critical: e.target.checked }))} /> Critical dependency
            </label>
          </div>
          <Input label="Description" value={dependencyForm.description} onChange={(e) => setDependencyForm((prev) => ({ ...prev, description: e.target.value }))} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setDependencyService(null)}>Cancel</Button>
            <Button type="submit" loading={addDependencyMutation.isPending} disabled={!dependencyForm.target_service_id}>Add dependency</Button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(memberService)} onClose={() => setMemberService(null)} title={`Add member${memberService ? ` to ${memberService.name}` : ''}`} size="lg">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); addMemberMutation.mutate(); }}>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Select label="Member type" options={[{ value: 'device', label: 'Device' }, { value: 'interface', label: 'Interface' }]} value={memberForm.member_mode} onChange={(e) => setMemberForm((prev) => ({ ...prev, member_mode: e.target.value as MemberMode, interface_id: '' }))} />
            <Select label="Device" required options={requiredDeviceOptions} value={memberForm.device_id} onChange={(e) => setMemberForm((prev) => ({ ...prev, device_id: e.target.value, interface_id: '' }))} />
            {memberForm.member_mode === 'interface' && <Select label="Interface" required options={memberInterfaceOptions} value={memberForm.interface_id} onChange={(e) => setMemberForm((prev) => ({ ...prev, interface_id: e.target.value }))} />}
            <Input label="Role" value={memberForm.role} onChange={(e) => setMemberForm((prev) => ({ ...prev, role: e.target.value }))} />
            <Input label="Weight" type="number" min="0.1" step="0.1" value={memberForm.weight} onChange={(e) => setMemberForm((prev) => ({ ...prev, weight: e.target.value }))} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setMemberService(null)}>Cancel</Button>
            <Button type="submit" loading={addMemberMutation.isPending} disabled={memberForm.member_mode === 'interface' ? !memberForm.interface_id : !memberForm.device_id}>Add member</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function interfaceLabel(iface: ManagedInterface) {
  const index = iface.if_index == null ? '' : `#${iface.if_index} · `;
  const status = iface.oper_status ? ` · ${iface.oper_status}` : '';
  return `${index}${iface.name}${iface.alias ? ` (${iface.alias})` : ''}${status}`;
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-3 py-2 align-top text-gray-700 dark:text-gray-200">{children}</td>;
}

export default ServicesPage;
