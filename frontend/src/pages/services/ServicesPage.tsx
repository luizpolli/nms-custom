import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Layers3, Waypoints } from 'lucide-react';
import { Badge, Card, EmptyState, PageHeader, Spinner, StatCard } from '../../components/ui';
import { api } from '../../lib/api';

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

type ServiceImpact = {
  service_id: string;
  name: string;
  kind: string;
  description?: string | null;
  score: number;
  health_state: string;
  member_count: number;
  impacted_member_count: number;
  active_alarm_count: number;
  worst_severity: string;
  members: ServiceImpactMember[];
};

export function ServicesPage() {
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

  const impactById = useMemo(() => new Map((impactQuery.data ?? []).map((item) => [item.service_id, item])), [impactQuery.data]);
  const services = servicesQuery.data ?? [];
  const impactedCount = (impactQuery.data ?? []).filter((svc) => svc.impacted_member_count > 0 || svc.score < 100).length;
  const averageScore = impactQuery.data?.length
    ? Math.round(impactQuery.data.reduce((sum, svc) => sum + svc.score, 0) / impactQuery.data.length)
    : 100;

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Services"
        subtitle="Logical service inventory with live assurance impact from member alarms and interface health"
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
          <EmptyState title="No services modeled" description="Create services through the API to group devices/interfaces and calculate customer, transport, or platform impact." />
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
                      <Td>{impact ? `${impact.impacted_member_count} members · ${impact.active_alarm_count} alarms` : 'pending score'}</Td>
                      <Td>{new Date(service.updated_at).toLocaleString()}</Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {(impactQuery.data ?? []).slice(0, 4).map((service) => (
          <Card key={service.service_id} className="p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">{service.name}</h3>
                <p className="text-xs text-gray-500">{service.kind} · {service.health_state}</p>
              </div>
              <Badge variant={service.score >= 90 ? 'success' : service.score >= 75 ? 'warning' : 'danger'}>{service.score}</Badge>
            </div>
            {!service.members.length ? (
              <EmptyState title="No members" description="Add devices or interfaces to include this service in impact scoring." />
            ) : (
              <div className="space-y-2">
                {service.members.slice(0, 6).map((member) => (
                  <div key={member.member_id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-700">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-gray-900 dark:text-white">{member.label}</div>
                      <div className="text-xs text-gray-500">{member.role} · weight {member.weight}</div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant={(member.worst_severity || 'info') as never}>{member.worst_severity}</Badge>
                      <Badge variant={member.score >= 90 ? 'success' : member.score >= 75 ? 'warning' : 'danger'}>{member.score}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>
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
