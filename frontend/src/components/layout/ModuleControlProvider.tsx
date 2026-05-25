import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api } from '../../lib/api';
import { MODULE_DEFAULTS, moduleByKey, type ModuleControlSettings, type ModuleKey } from '../../lib/moduleControls';

interface ModuleControlContextValue {
  modules: ModuleControlSettings;
  loading: boolean;
  isEnabled: (key: ModuleKey) => boolean;
  moduleLabel: (key: ModuleKey) => string;
  refresh: () => Promise<void>;
}

const ModuleControlContext = createContext<ModuleControlContextValue | null>(null);

function normalizeModules(value: Partial<ModuleControlSettings> | null | undefined): ModuleControlSettings {
  return { ...MODULE_DEFAULTS, ...(value || {}) };
}

export function ModuleControlProvider({ children }: { children: ReactNode }) {
  const [modules, setModules] = useState<ModuleControlSettings>(MODULE_DEFAULTS);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const response = await api.get('/settings/modules');
      setModules(normalizeModules(response.data));
    } catch {
      setModules(MODULE_DEFAULTS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    const handleModulesUpdated = (event: Event) => {
      const next = (event as CustomEvent<Partial<ModuleControlSettings>>).detail;
      setModules(normalizeModules(next));
    };
    window.addEventListener('nms-modules-updated', handleModulesUpdated);
    return () => window.removeEventListener('nms-modules-updated', handleModulesUpdated);
  }, []);

  const value = useMemo<ModuleControlContextValue>(() => ({
    modules,
    loading,
    isEnabled: (key) => modules[key] !== false,
    moduleLabel: (key) => moduleByKey[key]?.label || key,
    refresh,
  }), [modules, loading]);

  return <ModuleControlContext.Provider value={value}>{children}</ModuleControlContext.Provider>;
}

export function useModuleControls() {
  const context = useContext(ModuleControlContext);
  if (!context) {
    throw new Error('useModuleControls must be used inside ModuleControlProvider');
  }
  return context;
}
