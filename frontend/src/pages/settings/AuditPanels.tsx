/**
 * Settings Audit + Account Audit panels (P1.5 slice 3d).
 *
 * Extracted from Settings.tsx — zero behaviour changes.
 * SettingsAuditLog interface is co-located here since both panels consume it.
 */

import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { Card, CardHeader } from '../../components/ui/Card';
import { Input, Button, Badge, Select } from '../../components/ui';
import { api } from '../../lib/api';

// ─── Shared audit log type ────────────────────────────────────────────────────

export interface SettingsAuditLog {
  id: string;
  timestamp: string;
  actor?: string | null;
  action: string;
  object_id?: string | null;
  source_ip?: string | null;
  message?: string | null;
  outcome: string;
  details?: Record<string, unknown> | null;
}

// ─── Settings Audit (recent settings changes) ─────────────────────────────────

export function SettingsAuditPanel() {
  const [entries, setEntries] = useState<SettingsAuditLog[]>([]);

  useEffect(() => {
    api.get('/settings/audit?limit=8').then((r) => setEntries(r.data)).catch(() => setEntries([]));
  }, []);

  return (
    <Card>
      <CardHeader title="Recent Settings Audit" />
      <div className="overflow-x-auto p-4">
        <table className="min-w-full text-sm">
          <thead className="text-xs uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2 text-left">Time</th>
              <th className="px-3 py-2 text-left">Action</th>
              <th className="px-3 py-2 text-left">Target</th>
              <th className="px-3 py-2 text-left">Actor</th>
              <th className="px-3 py-2 text-left">Outcome</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td className="px-3 py-2 text-gray-500">{new Date(entry.timestamp).toLocaleString()}</td>
                <td className="px-3 py-2 font-medium">{entry.action}</td>
                <td className="px-3 py-2">{entry.object_id || '-'}</td>
                <td className="px-3 py-2">{entry.actor || 'system'}</td>
                <td className="px-3 py-2"><Badge variant={entry.outcome === 'success' ? 'success' : 'warning'}>{entry.outcome}</Badge></td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr><td className="px-3 py-4 text-gray-500" colSpan={5}>No settings audit events recorded yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ─── Account Audit (user activity log) ───────────────────────────────────────

export function AccountAuditPanel() {
  const [entries, setEntries] = useState<SettingsAuditLog[]>([]);
  const [filters, setFilters] = useState({ q: '', actor: '', action: '', role: '', outcome: '', since: '', until: '' });
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const queryParams = () => {
    const params = new URLSearchParams({ limit: '100' });
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    return params;
  };

  const loadAudit = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/settings/account-audit?${queryParams().toString()}`);
      setEntries(response.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAudit();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setFilter = (key: keyof typeof filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      const params = queryParams();
      params.set('format', 'csv');
      params.delete('limit');
      const response = await api.get(`/settings/account-audit/export?${params.toString()}`, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'account_audit_export.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const detailText = (entry: SettingsAuditLog, key: string) => {
    const value = entry.details?.[key];
    return typeof value === 'string' || typeof value === 'number' ? String(value) : '-';
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Account Activity" />
        <div className="space-y-4 p-4">
          <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-4">
            <Input placeholder="Search actor, action, path..." value={filters.q} onChange={(e) => setFilter('q', e.target.value)} />
            <Input placeholder="Actor" value={filters.actor} onChange={(e) => setFilter('actor', e.target.value)} />
            <Input placeholder="Action" value={filters.action} onChange={(e) => setFilter('action', e.target.value)} />
            <Select value={filters.role} onChange={(e) => setFilter('role', e.target.value)}>
              <option value="">Any role</option>
              <option value="root">Root</option>
              <option value="admin">Admin</option>
              <option value="operator">Operator</option>
              <option value="viewer">Viewer</option>
              <option value="ai-ops">AI Ops</option>
            </Select>
            <Select value={filters.outcome} onChange={(e) => setFilter('outcome', e.target.value)}>
              <option value="">Any outcome</option>
              <option value="success">Success</option>
              <option value="failure">Failure</option>
            </Select>
            <Input type="datetime-local" value={filters.since} onChange={(e) => setFilter('since', e.target.value)} />
            <Input type="datetime-local" value={filters.until} onChange={(e) => setFilter('until', e.target.value)} />
            <div className="flex gap-2">
              <Button variant="secondary" onClick={loadAudit} loading={loading}>Apply</Button>
              <Button variant="outline" onClick={exportCsv} loading={exporting} leftIcon={<Download className="h-4 w-4" />}>Export</Button>
            </div>
          </div>

          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500 dark:bg-gray-800">
                <tr>
                  {['Time', 'Actor', 'Role', 'Action', 'Outcome', 'Source IP', 'Path'].map((header) => (
                    <th key={header} className="px-3 py-2 text-left">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="px-3 py-2 text-gray-500">{new Date(entry.timestamp).toLocaleString()}</td>
                    <td className="px-3 py-2 font-medium">{entry.actor || '-'}</td>
                    <td className="px-3 py-2">{detailText(entry, 'role')}</td>
                    <td className="px-3 py-2">{entry.action}</td>
                    <td className="px-3 py-2"><Badge variant={entry.outcome === 'success' ? 'success' : 'danger'}>{entry.outcome}</Badge></td>
                    <td className="px-3 py-2">{entry.source_ip || '-'}</td>
                    <td className="px-3 py-2">{detailText(entry, 'path')}</td>
                  </tr>
                ))}
                {entries.length === 0 && (
                  <tr><td className="px-3 py-4 text-gray-500" colSpan={7}>No account audit events match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </Card>
    </div>
  );
}
