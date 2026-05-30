/**
 * NOC Board — full-screen, TV-optimized dashboard.
 * Large alarm feed, traffic light indicators, assurance score, alarm counts.
 * Auto-refreshes every 10 seconds; WebSocket-driven alarm feed.
 */

import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { X, Maximize2, Minimize2 } from 'lucide-react';
import { api } from '../lib/api';
import { useAlarmWebSocket } from '../lib/ws';
import type { Alarm, AlarmSummary } from '../lib/types';

// ─── API types ────────────────────────────────────────────────────────────────

interface AssuranceSummary {
  network_score: number;
  health_state: string;
}

interface ServiceImpact {
  service_id: string;
  name: string;
  score: number;
  health_state: string;
}

interface Device {
  id: string;
  name: string;
  status: string;
}

// ─── Query hooks ─────────────────────────────────────────────────────────────

const REFRESH = 10_000;

function useAlarmSummary() {
  return useQuery({
    queryKey: ['noc', 'alarm-summary'],
    queryFn: () => api.get<AlarmSummary>('/alarms/summary').then((r) => r.data),
    refetchInterval: REFRESH,
  });
}

function useRecentAlarms() {
  return useQuery({
    queryKey: ['noc', 'recent-alarms'],
    queryFn: () => api.get<Alarm[]>('/alarms', { params: { limit: 50 } }).then((r) => r.data),
    refetchInterval: REFRESH,
  });
}

function useAssurance() {
  return useQuery({
    queryKey: ['noc', 'assurance'],
    queryFn: () => api.get<AssuranceSummary>('/assurance/summary').then((r) => r.data),
    refetchInterval: REFRESH,
  });
}

function useServices() {
  return useQuery({
    queryKey: ['noc', 'services'],
    queryFn: () => api.get<ServiceImpact[]>('/assurance/services').then((r) => r.data),
    refetchInterval: REFRESH,
  });
}

function useDevices() {
  return useQuery({
    queryKey: ['noc', 'devices'],
    queryFn: () => api.get<Device[]>('/devices', { params: { limit: 200 } }).then((r) => r.data),
    refetchInterval: REFRESH,
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SEVERITY_ORDER = ['critical', 'major', 'minor', 'warning', 'info'];

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  major: '#f97316',
  minor: '#eab308',
  warning: '#3b82f6',
  info: '#6b7280',
};

const SEVERITY_BG: Record<string, string> = {
  critical: 'bg-red-900/40 border-red-500/50',
  major: 'bg-orange-900/40 border-orange-500/50',
  minor: 'bg-yellow-900/40 border-yellow-500/50',
  warning: 'bg-blue-900/40 border-blue-500/50',
  info: 'bg-gray-800/60 border-gray-600/50',
};

function severityDot(severity: string, size = 'md') {
  const color = SEVERITY_COLORS[severity] ?? '#6b7280';
  const cls = size === 'sm' ? 'h-2 w-2' : 'h-3 w-3';
  return (
    <span
      className={`inline-block ${cls} rounded-full`}
      style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
    />
  );
}

function trafficLight(score: number) {
  if (score >= 90) return { color: '#10b981', label: 'HEALTHY', glow: '0 0 16px #10b981' };
  if (score >= 70) return { color: '#f59e0b', label: 'DEGRADED', glow: '0 0 16px #f59e0b' };
  return { color: '#ef4444', label: 'CRITICAL', glow: '0 0 16px #ef4444' };
}

function timeAgo(value?: string) {
  if (!value) return '—';
  const ts = new Date(value).getTime();
  if (Number.isNaN(ts)) return '—';
  const seconds = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h`;
}

// ─── Alarm ticker (auto-scroll) ───────────────────────────────────────────────

function AlarmTicker({
  alarms,
  wsAlarm,
}: {
  alarms: Alarm[];
  wsAlarm: Alarm | null;
}) {
  const listRef = useRef<HTMLUListElement>(null);
  const [feed, setFeed] = useState<Alarm[]>([]);

  // Initialize feed from query data
  useEffect(() => {
    setFeed(alarms.slice(0, 30));
  }, [alarms]);

  // Prepend WebSocket alarms in real time
  useEffect(() => {
    if (!wsAlarm) return;
    setFeed((prev) => {
      if (prev[0]?.id === wsAlarm.id) return prev;
      return [wsAlarm, ...prev].slice(0, 40);
    });
  }, [wsAlarm]);

  // Auto-scroll to top when new WS alarm arrives
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0;
    }
  }, [wsAlarm]);

  return (
    <ul
      ref={listRef}
      className="divide-y divide-gray-700/50 overflow-y-auto"
      style={{ maxHeight: '100%' }}
    >
      {feed.map((alarm) => (
        <li
          key={alarm.id}
          className={`flex items-start gap-3 border-l-2 px-4 py-3 ${SEVERITY_BG[alarm.severity] ?? 'bg-gray-800/40 border-gray-600/40'}`}
          style={{ borderLeftColor: SEVERITY_COLORS[alarm.severity] ?? '#6b7280' }}
        >
          {severityDot(alarm.severity)}
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-sm font-semibold text-white">
                {alarm.source_host ?? alarm.source ?? 'unknown'}
              </span>
              <span className="shrink-0 text-xs text-gray-400">{timeAgo(alarm.last_seen ?? alarm.raised_at)}</span>
            </div>
            <div className="truncate text-xs text-gray-400">{alarm.message}</div>
          </div>
        </li>
      ))}
      {!feed.length && (
        <li className="px-4 py-8 text-center text-sm text-gray-500">No active alarms</li>
      )}
    </ul>
  );
}

// ─── Big number counter ───────────────────────────────────────────────────────

function SeverityCounter({
  severity,
  count,
}: {
  severity: string;
  count: number;
}) {
  const color = SEVERITY_COLORS[severity] ?? '#6b7280';
  return (
    <div
      className="flex flex-col items-center rounded-xl border px-6 py-4"
      style={{
        borderColor: `${color}40`,
        backgroundColor: `${color}15`,
        boxShadow: count > 0 ? `0 0 20px ${color}30` : 'none',
      }}
    >
      <span
        className="text-4xl font-black tabular-nums"
        style={{ color, textShadow: count > 0 ? `0 0 12px ${color}` : 'none' }}
      >
        {count}
      </span>
      <span className="mt-1 text-xs font-semibold uppercase tracking-widest text-gray-400">
        {severity}
      </span>
    </div>
  );
}

// ─── Assurance score ring ─────────────────────────────────────────────────────

function AssuranceRing({ score, healthState }: { score: number; healthState: string }) {
  const { color, label, glow } = trafficLight(score);
  const r = 42;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative">
        <svg width="120" height="120" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={r} fill="none" stroke="#374151" strokeWidth="10" />
          <circle
            cx="50"
            cy="50"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 50 50)"
            style={{ filter: `drop-shadow(${glow})`, transition: 'stroke-dashoffset 0.6s ease' }}
          />
          <text x="50" y="45" textAnchor="middle" fontSize="22" fontWeight="bold" fill={color}>
            {score}
          </text>
          <text x="50" y="62" textAnchor="middle" fontSize="8" fill="#9ca3af">
            SCORE
          </text>
        </svg>
      </div>
      <span
        className="text-xs font-bold uppercase tracking-widest"
        style={{ color, textShadow: glow }}
      >
        {label}
      </span>
      <span className="text-xs text-gray-500 capitalize">{healthState}</span>
    </div>
  );
}

// ─── Device status pills ──────────────────────────────────────────────────────

function DeviceStatusSummary({ devices }: { devices: Device[] }) {
  const counts = { reachable: 0, unreachable: 0, polling: 0, unknown: 0 } as Record<string, number>;
  devices.forEach((d) => { counts[d.status] = (counts[d.status] ?? 0) + 1; });
  return (
    <div className="flex flex-wrap gap-3 justify-center">
      {[
        { k: 'reachable', label: 'UP', color: '#10b981' },
        { k: 'unreachable', label: 'DOWN', color: '#ef4444' },
        { k: 'polling', label: 'POLLING', color: '#3b82f6' },
        { k: 'unknown', label: 'UNKNOWN', color: '#6b7280' },
      ].map(({ k, label, color }) => (
        <div
          key={k}
          className="rounded-lg border px-4 py-2 text-center"
          style={{ borderColor: `${color}40`, backgroundColor: `${color}12` }}
        >
          <div className="text-xl font-black tabular-nums" style={{ color }}>{counts[k] ?? 0}</div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-gray-400">{label}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Service traffic lights ───────────────────────────────────────────────────

function ServiceLights({ services }: { services: ServiceImpact[] }) {
  return (
    <div className="flex flex-wrap gap-3">
      {services.slice(0, 12).map((svc) => {
        const { color, glow } = trafficLight(svc.score);
        return (
          <div
            key={svc.service_id}
            className="flex items-center gap-2 rounded-lg border border-gray-700/50 bg-gray-800/40 px-3 py-2"
          >
            <span
              className="h-3 w-3 shrink-0 rounded-full"
              style={{ backgroundColor: color, boxShadow: glow }}
            />
            <div className="min-w-0">
              <div className="max-w-[120px] truncate text-xs font-medium text-white">{svc.name}</div>
              <div className="text-[10px] text-gray-400">{svc.score}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main NOC Board ───────────────────────────────────────────────────────────

export function NOCBoard() {
  const navigate = useNavigate();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [now, setNow] = useState(new Date());

  const alarmSummary = useAlarmSummary();
  const recentAlarms = useRecentAlarms();
  const assurance = useAssurance();
  const services = useServices();
  const devices = useDevices();
  const ws = useAlarmWebSocket();

  // Live clock
  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Fullscreen API
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, []);

  const summary = alarmSummary.data;
  const asmScore = assurance.data?.network_score ?? 0;
  const asmState = assurance.data?.health_state ?? 'unknown';

  return (
    <div className="flex h-full min-h-screen flex-col bg-gray-950 text-white">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-gray-800 bg-gray-900/80 px-6 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <span className="text-lg font-black uppercase tracking-widest text-white">
            NOC Board
          </span>
          <span className="rounded bg-gray-800 px-2 py-0.5 text-xs font-mono text-gray-300">
            {now.toLocaleTimeString()}
          </span>
          <span className="text-xs text-gray-500">
            {now.toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' })}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Auto-refresh: 10s</span>
          <button
            type="button"
            onClick={toggleFullscreen}
            className="rounded p-1.5 text-gray-400 hover:bg-gray-800 hover:text-white"
            title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          >
            {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </button>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="rounded p-1.5 text-gray-400 hover:bg-gray-800 hover:text-white"
            title="Exit NOC Board"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Main grid */}
      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Left: alarm feed */}
        <div className="flex w-80 shrink-0 flex-col border-r border-gray-800">
          <div className="border-b border-gray-800 bg-gray-900/60 px-4 py-2">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-widest text-gray-400">Live Alarms</h2>
              {ws.connected && (
                <span className="flex items-center gap-1 text-xs text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  LIVE
                </span>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-hidden">
            <AlarmTicker
              alarms={recentAlarms.data ?? []}
              wsAlarm={ws.lastAlarm}
            />
          </div>
        </div>

        {/* Center: big numbers + charts */}
        <div className="flex flex-1 flex-col gap-0">
          {/* Severity counters */}
          <div className="border-b border-gray-800 bg-gray-900/40 p-6">
            <h2 className="mb-4 text-xs font-bold uppercase tracking-widest text-gray-500">Active Alarms by Severity</h2>
            <div className="flex flex-wrap justify-center gap-4">
              {SEVERITY_ORDER.map((sev) => (
                <SeverityCounter
                  key={sev}
                  severity={sev}
                  count={
                    (summary as Record<string, number> | undefined)?.[sev] ??
                    (summary?.by_severity as Record<string, number> | undefined)?.[sev] ??
                    0
                  }
                />
              ))}
            </div>
          </div>

          {/* Services traffic lights */}
          <div className="border-b border-gray-800 bg-gray-900/20 p-6">
            <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-gray-500">Service Health</h2>
            {services.data?.length ? (
              <ServiceLights services={services.data} />
            ) : (
              <p className="text-xs text-gray-600">No service data</p>
            )}
          </div>

          {/* Device status */}
          <div className="flex-1 p-6">
            <h2 className="mb-4 text-xs font-bold uppercase tracking-widest text-gray-500">Device Status</h2>
            {devices.data ? (
              <DeviceStatusSummary devices={devices.data} />
            ) : (
              <p className="text-xs text-gray-600">Loading…</p>
            )}
          </div>
        </div>

        {/* Right: assurance score */}
        <div className="flex w-56 shrink-0 flex-col items-center justify-start gap-6 border-l border-gray-800 bg-gray-900/40 p-6">
          <div className="w-full">
            <h2 className="mb-4 text-center text-xs font-bold uppercase tracking-widest text-gray-500">Assurance</h2>
            {assurance.data ? (
              <AssuranceRing score={asmScore} healthState={asmState} />
            ) : (
              <div className="h-32 w-full animate-pulse rounded-full bg-gray-800" />
            )}
          </div>

          <div className="w-full border-t border-gray-800 pt-4">
            <div className="text-center text-xs font-bold uppercase tracking-widest text-gray-500 mb-3">Total</div>
            <div className="text-center">
              <div className="text-5xl font-black tabular-nums text-white">
                {((summary as Record<string, number> | undefined)?.total) ??
                  Object.values((summary?.by_severity as Record<string, number>) ?? {}).reduce((a, b) => a + b, 0)}
              </div>
              <div className="mt-1 text-xs text-gray-500 uppercase tracking-wider">Active alarms</div>
            </div>
          </div>

          {ws.lastAlarm && (
            <div
              className="w-full rounded-lg border border-red-500/30 bg-red-900/20 p-3"
              style={{ boxShadow: '0 0 12px rgba(239,68,68,0.2)' }}
            >
              <div className="mb-1 text-[10px] font-bold uppercase tracking-widest text-red-400">Last Event</div>
              <div className="flex items-center gap-1.5">
                {severityDot(ws.lastAlarm.severity, 'sm')}
                <span className="text-xs font-medium text-white truncate">
                  {ws.lastAlarm.source_host ?? ws.lastAlarm.source ?? 'unknown'}
                </span>
              </div>
              <div className="mt-0.5 truncate text-[10px] text-gray-400">{ws.lastAlarm.message}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default NOCBoard;
