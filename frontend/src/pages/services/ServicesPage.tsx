import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, GitBranch, Info, Layers3, Plus, Trash2, Waypoints } from 'lucide-react';
import { Badge, Button, Card, EmptyState, InfoFloat, Input, Modal, PageHeader, PageIntroFloat, Select, Spinner, StatCard } from '../../components/ui';
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
  target_score?: number | null;
  member_count: number;
  created_at: string;
  updated_at: string;
  members: ServiceMember[];
  dependencies: ServiceDependency[];
};

type ServiceAlert = {
  service_id: string;
  name: string;
  kind: string;
  score: number;
  target_score: number;
  deficit: number;
  health_state: string;
  worst_severity: string;
  impacted_member_count: number;
  active_alarm_count: number;
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
  target_score: string;
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
  target_score: '',
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

const EXAMPLE_SERVICE_NAMES = [
  'Example - Core Transport',
  'Example - Customer MPLS ACME',
  'Example - Internet Edge',
];

const SERVICES_HELP = {
  overview: 'Services map technical network objects into logical business or operational services. Add devices/interfaces as members, define dependencies, then Assurance scores each service from alarms, interface health, and propagated dependency impact.',
  modeled: 'Total logical services configured. A service can represent a customer, transport domain, platform, infrastructure layer, or any operational grouping.',
  averageScore: 'Average health score across modeled services. Scores are calculated from member health, active alarms, and dependency penalties.',
  impacted: 'Services with degraded score or impacted members. This is the quick answer to which customer/platform/transport domain is affected.',
  exampleDiagram: 'A compact map of the sample service relationship. Customer and platform services depend on Core Transport, so transport degradation can propagate impact.',
  dependencyGraph: 'Directed edges between services. Use this to model blast radius, for example Customer VPN depends on Core Transport.',
  impactMatrix: 'Operational table that combines configured service metadata with live Assurance impact, score, alarms, and actions.',
  alerts: 'Services below their target score. If a service has no custom target, the default threshold is 90.',
  serviceCards: 'Per-service detail cards with trend, dependencies, members, current score, and target threshold.',
  createService: 'Create a logical service and optionally attach the first device or interface member.',
  addDependency: 'Declare that this service depends on another service. If the target degrades, the source can receive a propagated penalty.',
  addMember: 'Attach a device or interface to the service. Members are the actual network objects that drive the service score.',
};
const SERVICES_INTRO_STORAGE_KEY = 'nms-services-intro-dismissed-v2';

function PanelTitle({ title, description, icon, right }: { title: string; description: string; icon?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        {icon}
        <h2 className="truncate text-sm font-semibold text-gray-900 dark:text-white">{title}</h2>
        <InfoFloat title={title} description={description} />
      </div>
      {right}
    </div>
  );
}

function InfoStatCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="relative">
      {children}
      <div className="absolute right-3 top-3">
        <InfoFloat title={title} description={description} />
      </div>
    </div>
  );
}

function ExampleServiceDiagram({ services, impactById, framed = true }: { services: ServiceRecord[]; impactById: Map<string, ServiceImpact>; framed?: boolean }) {
  const exampleServices = EXAMPLE_SERVICE_NAMES.map((name) => services.find((service) => service.name === name));
  const [core, customer, internet] = exampleServices;
  const scoreFor = (service?: ServiceRecord) => service ? (impactById.get(service.id)?.score ?? 100) : null;
  const content = (
    <>
      <PanelTitle title="Example service map" description={SERVICES_HELP.exampleDiagram} icon={<GitBranch className="h-4 w-4" />} />
      <div className="grid grid-cols-1 items-center gap-3 lg:grid-cols-[1fr_auto_1fr]">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-1">
          <DiagramNode service={customer} fallback="Example - Customer MPLS ACME" kind="customer" score={scoreFor(customer)} />
          <DiagramNode service={internet} fallback="Example - Internet Edge" kind="platform" score={scoreFor(internet)} />
        </div>
        <div className="flex items-center justify-center text-xs font-semibold uppercase tracking-wide text-gray-400 lg:h-full lg:flex-col">
          <span className="hidden lg:block">depends on</span>
          <span className="text-2xl leading-none text-cisco-blue lg:rotate-0">-&gt;</span>
          <span className="lg:hidden">depends on</span>
        </div>
        <DiagramNode service={core} fallback="Example - Core Transport" kind="transport" score={scoreFor(core)} large />
      </div>
    </>
  );

  return framed ? <Card className="p-4">{content}</Card> : <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-950">{content}</div>;
}

function scoreBadgeTone(score: number | null) {
  return score == null ? 'default' : score >= 90 ? 'success' : score >= 75 ? 'warning' : 'danger';
}

function DiagramNode({ service, fallback, kind, score, large = false }: { service?: ServiceRecord; fallback: string; kind: string; score: number | null; large?: boolean }) {
  return (
    <div className={`rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900 ${large ? 'min-h-28' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-gray-900 dark:text-white">{service?.name ?? fallback}</div>
          <div className="mt-1 text-xs text-gray-500">{service ? `${service.member_count} member${service.member_count === 1 ? '' : 's'}` : 'not loaded yet'} · {service?.kind ?? kind}</div>
        </div>
        <Badge variant={scoreBadgeTone(score) as never}>{score ?? '—'}</Badge>
      </div>
      <div className="mt-3 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800">
        <div
          className={`h-1.5 rounded-full ${score == null ? 'bg-gray-300' : score >= 90 ? 'bg-green-500' : score >= 75 ? 'bg-yellow-500' : 'bg-red-500'}`}
          style={{ width: `${score ?? 0}%` }}
        />
      </div>
    </div>
  );
}

export function ServicesPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [showIntro, setShowIntro] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(SERVICES_INTRO_STORAGE_KEY) !== 'true';
  });
  const [memberService, setMemberService] = useState<ServiceRecord | null>(null);
  const [dependencyService, setDependencyService] = useState<ServiceRecord | null>(null);
  const [form, setForm] = useState<ServiceForm>(EMPTY_FORM);
  const [memberForm, setMemberForm] = useState<{ member_mode: MemberMode; device_id: string; interface_id: string; role: string; weight: string }>({ member_mode: 'device', device_id: '', interface_id: '', role: 'member', weight: '1' });
  const [dependencyForm, setDependencyForm] = useState({ target_service_id: '', dependency_type: 'depends_on', direction: 'source_to_target', weight: '1', is_critical: false, description: '' });
  const [dependencyFilter, setDependencyFilter] = useState<'all' | 'impacted' | 'critical'>('all');

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
  const alertsQuery = useQuery({
    queryKey: ['assurance-service-alerts'],
    queryFn: () => api.get<ServiceAlert[]>('/assurance/service-alerts').then((r) => r.data),
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
    queryClient.invalidateQueries({ queryKey: ['assurance-service-alerts'] });
  };

  const updateTargetMutation = useMutation({
    mutationFn: ({ serviceId, target }: { serviceId: string; target: number | null }) =>
      api.patch(`/services/${serviceId}`, { target_score: target }),
    onSuccess: invalidateServices,
    onError: (err) => {
      console.error('Update target score failed', err);
      alert('Failed to update service target score');
    },
  });

  const handleSetTarget = (service: ServiceRecord) => {
    const current = service.target_score == null ? '' : String(service.target_score);
    const raw = window.prompt(
      `Target score for "${service.name}" (0-100, empty to clear)`,
      current,
    );
    if (raw === null) return;
    const trimmed = raw.trim();
    if (trimmed === '') {
      updateTargetMutation.mutate({ serviceId: service.id, target: null });
      return;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) {
      alert('Target score must be between 0 and 100');
      return;
    }
    updateTargetMutation.mutate({ serviceId: service.id, target: Math.round(parsed) });
  };

  const createMutation = useMutation({
    mutationFn: (body: ServiceForm) => {
      const memberPayload = body.member_mode === 'interface'
        ? (body.interface_id ? { interface_id: body.interface_id, role: body.role || 'member', weight: Number(body.weight) || 1 } : null)
        : (body.device_id ? { device_id: body.device_id, role: body.role || 'member', weight: Number(body.weight) || 1 } : null);
      const members = memberPayload ? [memberPayload] : [];
      const parsedTarget = body.target_score === '' ? null : Number(body.target_score);
      return api.post('/services', {
        name: body.name,
        kind: body.kind,
        description: body.description || null,
        target_score: parsedTarget !== null && Number.isFinite(parsedTarget) ? parsedTarget : null,
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
  const alertById = useMemo(() => new Map((alertsQuery.data ?? []).map((item) => [item.service_id, item])), [alertsQuery.data]);
  const alerts = alertsQuery.data ?? [];
  const deviceById = useMemo(() => new Map((devicesQuery.data ?? []).map((device) => [device.id, device])), [devicesQuery.data]);
  const deviceOptions = [{ value: '', label: 'No initial member' }, ...(devicesQuery.data ?? []).map((device) => ({ value: device.id, label: `${device.name} (${device.ip_address})` }))];
  const requiredDeviceOptions = [{ value: '', label: 'Select device…' }, ...(devicesQuery.data ?? []).map((device) => ({ value: device.id, label: `${device.name} (${device.ip_address})` }))];
  const createInterfaceOptions = [{ value: '', label: createInterfacesQuery.isFetching ? 'Loading interfaces…' : 'Select interface…' }, ...(createInterfacesQuery.data ?? []).map((iface) => ({ value: iface.id, label: interfaceLabel(iface) }))];
  const memberInterfaceOptions = [{ value: '', label: memberInterfacesQuery.isFetching ? 'Loading interfaces…' : 'Select interface…' }, ...(memberInterfacesQuery.data ?? []).map((iface) => ({ value: iface.id, label: interfaceLabel(iface) }))];
  const services = servicesQuery.data ?? [];
  const dependencyTargetOptions = [{ value: '', label: 'Select target service…' }, ...services.filter((svc) => svc.id !== dependencyService?.id).map((svc) => ({ value: svc.id, label: `${svc.name} (${svc.kind})` }))];
  const dependencyEdges = services.flatMap((service) => (service.dependencies ?? []).map((dependency) => ({ service, dependency, impact: impactById.get(service.id) })));
  const filteredDependencyEdges = dependencyEdges.filter(({ dependency, impact }) => {
    if (dependencyFilter === 'critical') return dependency.is_critical;
    if (dependencyFilter === 'impacted') return Boolean(impact?.dependency_impacts?.some((item) => item.dependency_id === dependency.id));
    return true;
  });
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

      {showIntro && (
        <PageIntroFloat
          title="Services summary"
          icon={<Info className="h-4 w-4 text-cisco-blue" />}
          onDismiss={({ dontShowAgain }) => {
            if (dontShowAgain) window.localStorage.setItem(SERVICES_INTRO_STORAGE_KEY, 'true');
            setShowIntro(false);
          }}
        >
          <p className="mb-3 text-gray-600 dark:text-gray-300">{SERVICES_HELP.overview}</p>
          <ExampleServiceDiagram services={services} impactById={impactById} framed={false} />
        </PageIntroFloat>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <InfoStatCard title="Services modeled" description={SERVICES_HELP.modeled}>
          <StatCard title="Services modeled" value={services.length} icon={<Layers3 className="h-5 w-5" />} loading={servicesQuery.isLoading} />
        </InfoStatCard>
        <InfoStatCard title="Average score" description={SERVICES_HELP.averageScore}>
          <StatCard title="Average score" value={impactQuery.isLoading ? '—' : averageScore} icon={<Activity className="h-5 w-5" />} tone={averageScore >= 90 ? 'success' : averageScore >= 75 ? 'warning' : 'danger'} loading={impactQuery.isLoading} />
        </InfoStatCard>
        <InfoStatCard title="Impacted services" description={SERVICES_HELP.impacted}>
          <StatCard title="Impacted services" value={impactedCount} icon={<Waypoints className="h-5 w-5" />} tone={impactedCount ? 'warning' : 'success'} loading={impactQuery.isLoading} />
        </InfoStatCard>
      </div>

      <ExampleServiceDiagram services={services} impactById={impactById} />

      <Card className="p-4">
        <PanelTitle
          title="Dependency graph"
          description={SERVICES_HELP.dependencyGraph}
          icon={<GitBranch className="h-4 w-4" />}
          right={<Select className="w-40" value={dependencyFilter} onChange={(e) => setDependencyFilter(e.target.value as 'all' | 'impacted' | 'critical')} options={[{ value: 'all', label: 'All edges' }, { value: 'impacted', label: 'Impacted' }, { value: 'critical', label: 'Critical' }]} />}
        />
        {!dependencyEdges.length ? (
          <EmptyState title="No dependency edges" description="Add dependencies between services to visualize service-to-service blast radius." />
        ) : (
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {filteredDependencyEdges.map(({ service, dependency, impact }) => {
              const dependencyImpact = impact?.dependency_impacts?.find((item) => item.dependency_id === dependency.id);
              const targetScore = dependencyImpact?.target_score;
              return (
                <div key={dependency.id} className={`rounded-lg border p-3 text-sm ${dependencyImpact ? 'border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/20' : 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900'}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-semibold text-gray-900 dark:text-white">{service.name} → {dependency.target_service_name ?? dependency.target_service_id}</div>
                      <div className="text-xs text-gray-500">{dependency.dependency_type} · {dependency.direction} · weight {dependency.weight}{dependency.is_critical ? ' · critical' : ''}</div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {typeof targetScore === 'number' && <Badge variant={targetScore >= 90 ? 'success' : targetScore >= 75 ? 'warning' : 'danger'}>{targetScore}</Badge>}
                      {dependencyImpact && <Badge variant="danger">-{dependencyImpact.propagated_penalty}</Badge>}
                    </div>
                  </div>
                  {dependency.description && <p className="mt-2 text-xs text-gray-500">{dependency.description}</p>}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card className="p-4">
        <PanelTitle
          title="Service impact matrix"
          description={SERVICES_HELP.impactMatrix}
          right={(servicesQuery.isFetching || impactQuery.isFetching) && <Spinner size="sm" />}
        />

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

      {alerts.length > 0 && (
        <Card className="border-red-200 bg-red-50 p-4 dark:border-red-900/40 dark:bg-red-950/20">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
              <Activity className="h-4 w-4" /> {alerts.length} service{alerts.length === 1 ? '' : 's'} below target threshold
              <InfoFloat title="Service target alerts" description={SERVICES_HELP.alerts} />
            </div>
            <span className="text-xs text-red-600 dark:text-red-400">default target 90 · per-service overrides honored</span>
          </div>
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {alerts.slice(0, 8).map((alert) => (
              <li key={alert.service_id} className="flex items-center justify-between gap-3 rounded border border-red-200 bg-white px-3 py-2 text-sm dark:border-red-900/40 dark:bg-gray-900">
                <div className="min-w-0">
                  <div className="truncate font-medium text-gray-900 dark:text-white">{alert.name}</div>
                  <div className="text-xs text-gray-500">{alert.kind} · score {alert.score} / target {alert.target_score} · {alert.active_alarm_count} active alarm{alert.active_alarm_count === 1 ? '' : 's'}</div>
                </div>
                <Badge variant="danger">-{alert.deficit}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {services.map((service) => {
          const impact = impactById.get(service.id);
          const score = impact?.score ?? 100;
          const impactMembers = new Map((impact?.members ?? []).map((m) => [m.member_id, m]));
          const alert = alertById.get(service.id);
          const targetLabel = service.target_score == null ? 'default 90' : String(service.target_score);
          return (
            <Card key={service.id} className={`p-4 ${alert ? 'border-red-200 dark:border-red-900/40' : ''}`}>
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-gray-900 dark:text-white">{service.name}</h3>
                    <InfoFloat title={service.name} description={SERVICES_HELP.serviceCards} />
                  </div>
                  <p className="text-xs text-gray-500">{service.kind} · {impact?.health_state ?? 'pending'}{impact?.dependency_penalty ? ` · dependency penalty -${impact.dependency_penalty}` : ''}</p>
                  <button
                    type="button"
                    className="mt-1 text-xs text-blue-600 hover:underline dark:text-blue-400"
                    onClick={() => handleSetTarget(service)}
                    title="Set or clear target score"
                  >
                    target {targetLabel}
                  </button>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Badge variant={score >= 90 ? 'success' : score >= 75 ? 'warning' : 'danger'}>{score}</Badge>
                  {alert && <Badge variant="danger">breach -{alert.deficit}</Badge>}
                </div>
              </div>
              <div className="mb-3">
                <ServiceScoreSparkline serviceId={service.id} />
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
          <PanelTitle title="Create service" description={SERVICES_HELP.createService} />
          <Input label="Name" required value={form.name} onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))} />
          <Select label="Kind" options={KIND_OPTIONS} value={form.kind} onChange={(e) => setForm((prev) => ({ ...prev, kind: e.target.value }))} />
          <Input label="Description" value={form.description} onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))} />
          <Input
            label="Target score (0-100, optional)"
            type="number"
            min="0"
            max="100"
            step="1"
            placeholder="default 90"
            value={form.target_score}
            onChange={(e) => setForm((prev) => ({ ...prev, target_score: e.target.value }))}
          />
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
          <PanelTitle title="Add dependency" description={SERVICES_HELP.addDependency} />
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
          <PanelTitle title="Add member" description={SERVICES_HELP.addMember} />
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

type ScoreHistoryPoint = {
  captured_at: string;
  score: number;
  base_score: number | null;
  dependency_penalty: number;
  health_state: string;
};

function ServiceScoreSparkline({ serviceId }: { serviceId: string }) {
  const historyQuery = useQuery({
    queryKey: ['service-history', serviceId],
    queryFn: () =>
      api
        .get<ScoreHistoryPoint[]>(`/assurance/services/${serviceId}/history`, { params: { hours: 24 } })
        .then((r) => r.data),
    refetchInterval: 120_000,
    staleTime: 60_000,
  });

  const points = historyQuery.data ?? [];
  if (historyQuery.isLoading) {
    return <div className="h-10 w-full animate-pulse rounded bg-gray-100 dark:bg-gray-800" />;
  }
  if (points.length < 2) {
    return (
      <div className="flex h-10 items-center justify-center rounded border border-dashed border-gray-200 text-[11px] text-gray-400 dark:border-gray-700">
        no trend yet · history accumulates as scoring runs
      </div>
    );
  }

  const width = 240;
  const height = 40;
  const xs = points.map((_, i) => (points.length === 1 ? 0 : (i / (points.length - 1)) * width));
  const ys = points.map((p) => height - (Math.max(0, Math.min(100, p.score)) / 100) * height);
  const path = xs.map((x, i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(' ');
  const minScore = Math.min(...points.map((p) => p.score));
  const maxScore = Math.max(...points.map((p) => p.score));
  const lastScore = points[points.length - 1].score;
  const strokeColor = lastScore >= 90 ? '#16a34a' : lastScore >= 75 ? '#ca8a04' : '#dc2626';

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px] text-gray-500">
        <span>24h trend</span>
        <span>min {minScore} · max {maxScore} · n={points.length}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-10 w-full" preserveAspectRatio="none">
        <path d={path} fill="none" stroke={strokeColor} strokeWidth={1.5} />
      </svg>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-3 py-2 align-top text-gray-700 dark:text-gray-200">{children}</td>;
}

export default ServicesPage;
