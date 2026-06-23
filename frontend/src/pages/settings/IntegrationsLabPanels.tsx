/**
 * Module Controls + Integrations/AI Ops + Lab Operations panels (P1.5 slice 3c).
 *
 * Extracted from Settings.tsx — zero behaviour changes.
 */

import { Card, CardHeader } from '../../components/ui/Card';
import { Select } from '../../components/ui/Select';
import { Input, Badge, Button } from '../../components/ui';
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
                      <label className="inline-flex shrink-0 items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(event) => setModule(module.key, event.target.checked)}
                        />
                        <span>{enabled ? 'On' : 'Off'}</span>
                      </label>
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

// ─── Integrations / AI Ops ────────────────────────────────────────────────────

interface IntegrationsAiOpsAdminSettings {
  nbi_enabled: boolean;
  webhook_retry_attempts: number;
  webhook_timeout_seconds: number;
  ai_ops_enabled: boolean;
  ai_recommendation_min_confidence: number;
  llm_provider: 'local' | 'openai' | 'azure' | 'custom';
  llm_base_url: string;
  llm_model: string;
  llm_timeout_seconds: number;
  report_export_target_path: string;
}

const INTEGRATIONS_DEFAULTS: IntegrationsAiOpsAdminSettings = {
  nbi_enabled: true,
  webhook_retry_attempts: 3,
  webhook_timeout_seconds: 10,
  ai_ops_enabled: true,
  ai_recommendation_min_confidence: 70,
  llm_provider: 'local',
  llm_base_url: '',
  llm_model: '',
  llm_timeout_seconds: 30,
  report_export_target_path: '',
};

export function IntegrationsAiOpsSettingsPanel() {
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/integrations-ai-ops', INTEGRATIONS_DEFAULTS);
  const setIntegration = <K extends keyof IntegrationsAiOpsAdminSettings>(k: K, v: IntegrationsAiOpsAdminSettings[K]) =>
    setCfg((p) => ({ ...p, [k]: v }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Northbound API and Webhooks" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="flex items-center gap-2 md:col-span-3">
            <input type="checkbox" checked={cfg.nbi_enabled} onChange={(e) => setIntegration('nbi_enabled', e.target.checked)} />
            Enable northbound API access
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Webhook retries</span>
            <Input type="number" value={cfg.webhook_retry_attempts} onChange={(e) => setIntegration('webhook_retry_attempts', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Webhook timeout (seconds)</span>
            <Input type="number" value={cfg.webhook_timeout_seconds} onChange={(e) => setIntegration('webhook_timeout_seconds', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Report export target path</span>
            <Input value={cfg.report_export_target_path} onChange={(e) => setIntegration('report_export_target_path', e.target.value)} placeholder="/exports/reports" />
          </label>
          <div className="md:col-span-3">
            <SettingsHint>
              These fields are saved but not yet consumed by the backend — northbound forwarding is
              configured separately under Notifications &amp; Forwarding, which is the live implementation.
            </SettingsHint>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="AI Ops and LLM Provider" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="flex items-center gap-2 md:col-span-3">
            <input type="checkbox" checked={cfg.ai_ops_enabled} onChange={(e) => setIntegration('ai_ops_enabled', e.target.checked)} />
            Enable AI Ops recommendations
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">LLM provider</span>
            <Select value={cfg.llm_provider} onChange={(e) => setIntegration('llm_provider', e.target.value as IntegrationsAiOpsAdminSettings['llm_provider'])} disabled={!cfg.ai_ops_enabled}>
              <option value="local">Local (no external API)</option>
              <option value="openai">OpenAI</option>
              <option value="azure">Azure OpenAI</option>
              <option value="custom">Custom / OpenAI-compatible</option>
            </Select>
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Model name</span>
            <Input value={cfg.llm_model} onChange={(e) => setIntegration('llm_model', e.target.value)} placeholder="e.g. gpt-4o, llama3" disabled={!cfg.ai_ops_enabled} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Timeout (seconds)</span>
            <Input type="number" value={cfg.llm_timeout_seconds} onChange={(e) => setIntegration('llm_timeout_seconds', Number(e.target.value))} disabled={!cfg.ai_ops_enabled} />
          </label>
          <label className="block md:col-span-2">
            <span className="mb-1 block font-medium">Base URL</span>
            <Input
              value={cfg.llm_base_url}
              onChange={(e) => setIntegration('llm_base_url', e.target.value)}
              placeholder={cfg.llm_provider === 'custom' ? 'https://my-llm-proxy.example.com/v1' : 'Leave empty for provider default'}
              disabled={!cfg.ai_ops_enabled}
            />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Minimum confidence (%)</span>
            <Input type="number" value={cfg.ai_recommendation_min_confidence} onChange={(e) => setIntegration('ai_recommendation_min_confidence', Number(e.target.value))} disabled={!cfg.ai_ops_enabled} />
          </label>
          <div className="md:col-span-3">
            <SettingsHint>
              API keys and tokens must be configured via environment variables or a secret store — never entered here.
              This panel stores provider references and behaviour knobs for documentation purposes, but the running
              assistant currently reads its live configuration from the backend's AI_OPS_LLM_* environment variables —
              changes made here do not yet take effect until that wiring is added.
              The Base URL field accepts any OpenAI-compatible endpoint (e.g. a local Ollama proxy or a self-hosted vLLM instance).
            </SettingsHint>
          </div>
        </div>
      </Card>

      <SettingsSaveBar label="Save Integrations / AI Ops Settings" loading={loading} saving={saving} saved={saved} error={error} onSave={save} />
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
