/**
 * Module Controls + Integrations/AI Ops + Lab Operations panels (P1.5 slice 3c).
 *
 * Extracted from Settings.tsx — zero behaviour changes.
 */

import { Card, CardHeader } from '../../components/ui/Card';
import { Input, Badge, Button, Switch } from '../../components/ui';
import { useSettingsResource, SettingsSaveBar, SettingsHint } from './_shared';
import { MODULES, MODULE_DEFAULTS, type ModuleControlSettings, type ModuleKey } from '../../lib/moduleControls';
import { useModuleControls } from '../../components/layout/ModuleControlProvider';

// ─── Module Controls ──────────────────────────────────────────────────────────

export function ModuleControlSettingsPanel() {
  const moduleControls = useModuleControls();
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/modules', MODULE_DEFAULTS);
  const disabledCount = Object.values(cfg).filter((enabled) => !enabled).length;
  const groups = Array.from(new Set(MODULES.map((module) => module.group)));

  const setModule = (key: ModuleKey, enabled: boolean) => {
    setCfg((prev) => ({ ...prev, [key]: enabled }));
  };

  const setAll = (enabled: boolean) => {
    setCfg(MODULES.reduce((acc, module) => ({ ...acc, [module.key]: enabled }), {} as ModuleControlSettings));
  };

  const saveModules = async () => {
    const savedModules = await save();
    if (savedModules) {
      window.dispatchEvent(new CustomEvent('nms-modules-updated', { detail: savedModules }));
      await moduleControls.refresh();
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Customer Module Catalog" />
        <div className="space-y-4 p-4 text-sm">
          <SettingsHint>
            Disable modules a customer does not use. Disabled modules are removed from the sidebar and direct URL access shows a disabled-module screen. Settings remains always available so admins can re-enable modules.
          </SettingsHint>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-950">
            <div>
              <div className="font-semibold text-gray-900 dark:text-gray-100">Deployment profile</div>
              <div className="text-xs text-gray-500">
                {MODULES.length - disabledCount} enabled, {disabledCount} disabled
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setAll(true)}>Enable all</Button>
              <Button variant="outline" size="sm" onClick={() => setAll(false)}>Disable all operational modules</Button>
            </div>
          </div>

          {groups.map((group) => (
            <div key={group} className="rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="border-b border-gray-200 bg-gray-50 px-3 py-2 text-xs font-semibold uppercase text-gray-500 dark:border-gray-700 dark:bg-gray-800">
                {group}
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {MODULES.filter((module) => module.group === group).map((module) => {
                  const enabled = cfg[module.key] !== false;
                  return (
                    <div key={module.key} className="flex flex-col gap-3 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex min-w-0 items-start gap-3">
                        <span className={`mt-0.5 ${enabled ? 'text-cisco-blue' : 'text-gray-400'}`}>{module.icon}</span>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-gray-900 dark:text-gray-100">{module.label}</span>
                            <Badge variant={enabled ? 'success' : 'neutral'}>{enabled ? 'Enabled' : 'Disabled'}</Badge>
                            <span className="text-xs text-gray-400">{module.route}</span>
                          </div>
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{module.description}</p>
                        </div>
                      </div>
                      <Switch
                        checked={enabled}
                        onChange={(value) => setModule(module.key, value)}
                        label={enabled ? 'On' : 'Off'}
                        className="shrink-0"
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <SettingsSaveBar label="Save Module Controls" loading={loading} saving={saving || moduleControls.loading} saved={saved} error={error} onSave={saveModules} />
    </div>
  );
}

// ─── AI Ops ───────────────────────────────────────────────────────────────────

interface IntegrationsAiOpsAdminSettings {
  ai_ops_enabled: boolean;
  // Read-only — mirrors the backend's AI_OPS_LLM_* environment variables.
  // Connection details (model, base URL, API key) are infra-level config and
  // are never edited from this panel.
  effective_llm_enabled?: boolean;
  effective_llm_provider?: string;
  effective_llm_model?: string;
  effective_llm_base_url?: string;
}

const INTEGRATIONS_DEFAULTS: IntegrationsAiOpsAdminSettings = {
  ai_ops_enabled: true,
};

export function IntegrationsAiOpsSettingsPanel() {
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/integrations-ai-ops', INTEGRATIONS_DEFAULTS);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="AI Ops" />
        <div className="space-y-4 p-4 text-sm">
          <Switch
            checked={cfg.ai_ops_enabled}
            onChange={(value) => setCfg((p) => ({ ...p, ai_ops_enabled: value }))}
            label="Enable AI Ops recommendations"
          />

          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-950">
            <div className="mb-2 flex items-center gap-2 font-medium text-gray-900 dark:text-gray-100">
              Active LLM configuration
              <Badge variant={cfg.effective_llm_enabled ? 'success' : 'neutral'}>
                {cfg.effective_llm_enabled ? 'Connected' : 'Not configured'}
              </Badge>
            </div>
            <dl className="grid grid-cols-1 gap-2 text-xs text-gray-600 dark:text-gray-400 sm:grid-cols-2">
              <div>
                <dt className="font-medium">Provider</dt>
                <dd className="font-mono">{cfg.effective_llm_provider || '—'}</dd>
              </div>
              <div>
                <dt className="font-medium">Model</dt>
                <dd className="font-mono">{cfg.effective_llm_model || '—'}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="font-medium">Base URL</dt>
                <dd className="font-mono">{cfg.effective_llm_base_url || '—'}</dd>
              </div>
            </dl>
          </div>

          <SettingsHint>
            Provider, model, base URL, and API key are infrastructure config — set them via the
            backend's AI_OPS_LLM_* environment variables, never in this panel. The toggle above is
            the only knob this page controls; it's ANDed with the environment flag, so the
            assistant only answers questions when both are on.
          </SettingsHint>
        </div>
      </Card>

      <SettingsSaveBar label="Save AI Ops Settings" loading={loading} saving={saving} saved={saved} error={error} onSave={save} />
    </div>
  );
}

// ─── Lab Operations ───────────────────────────────────────────────────────────

interface LabOperationsAdminSettings {
  certification_mode_enabled: boolean;
  traffic_simulator_enabled: boolean;
  simulator_profile: string;
  maintenance_mode_enabled: boolean;
  maintenance_window: string;
  runbook_url: string;
  ptp_synce_enabled: boolean;
}

const LAB_OPERATIONS_DEFAULTS: LabOperationsAdminSettings = {
  certification_mode_enabled: true,
  traffic_simulator_enabled: false,
  simulator_profile: 'baseline',
  maintenance_mode_enabled: false,
  maintenance_window: '',
  runbook_url: '',
  ptp_synce_enabled: false,
};

export function LabOperationsSettingsPanel() {
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/lab-operations', LAB_OPERATIONS_DEFAULTS);
  const setLab = <K extends keyof LabOperationsAdminSettings>(k: K, v: LabOperationsAdminSettings[K]) =>
    setCfg((p) => ({ ...p, [k]: v }));

  return (
    <Card>
      <CardHeader title="Certification and Operations Controls" />
      <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.certification_mode_enabled} onChange={(e) => setLab('certification_mode_enabled', e.target.checked)} />
          Certification readiness mode
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.ptp_synce_enabled} onChange={(e) => setLab('ptp_synce_enabled', e.target.checked)} />
          Enable PTP / SyncE validation checks
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.traffic_simulator_enabled} onChange={(e) => setLab('traffic_simulator_enabled', e.target.checked)} />
          Traffic simulator hooks
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Simulator profile</span>
          <Input value={cfg.simulator_profile} onChange={(e) => setLab('simulator_profile', e.target.value)} disabled={!cfg.traffic_simulator_enabled} />
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.maintenance_mode_enabled} onChange={(e) => setLab('maintenance_mode_enabled', e.target.checked)} />
          Maintenance mode
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Maintenance window</span>
          <Input value={cfg.maintenance_window} onChange={(e) => setLab('maintenance_window', e.target.value)} placeholder="Sunday 01:00-03:00" disabled={!cfg.maintenance_mode_enabled} />
        </label>
        <label className="block md:col-span-2">
          <span className="mb-1 block font-medium">Runbook URL</span>
          <Input value={cfg.runbook_url} onChange={(e) => setLab('runbook_url', e.target.value)} placeholder="https://..." />
        </label>
        <div className="md:col-span-2">
          <SettingsSaveBar label="Save Lab / Operations Settings" loading={loading} saving={saving} saved={saved} error={error} onSave={save} />
        </div>
      </div>
    </Card>
  );
}
