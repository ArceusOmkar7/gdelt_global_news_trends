import { useState } from 'react';
import type { ChangeEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, RefreshCcw, SlidersHorizontal, Timer, HeartPulse, ChevronDown, ChevronUp } from 'lucide-react';

import { apiService } from '../../services/api';
import { useStore } from '../../store/useStore';

const FETCH_INTERVAL_OPTIONS = [15, 30, 60, 120];
const HEALTH_INTERVAL_OPTIONS = [15, 30, 60, 120];

export const SystemControlPanel = () => {
  const [open, setOpen] = useState(false); // collapsed by default

  const {
    autoRefreshEnabled,
    setAutoRefreshEnabled,
    fetchIntervalSeconds,
    setFetchIntervalSeconds,
    healthPollIntervalSeconds,
    setHealthPollIntervalSeconds,
    dateRange,
    eventRootCode,
  } = useStore();

  const healthQuery = useQuery({
    queryKey: ['health-status', healthPollIntervalSeconds],
    queryFn: apiService.getHealth,
    refetchInterval: healthPollIntervalSeconds * 1000,
    retry: 1,
  });

  const settingsQuery = useQuery({
    queryKey: ['runtime-settings'],
    queryFn: apiService.getRuntimeSettings,
    staleTime: 1000 * 60 * 5,
    retry: 1,
  });

  const health = healthQuery.data;

  const onAutoRefreshChange = (e: ChangeEvent<HTMLInputElement>) => setAutoRefreshEnabled(e.target.checked);
  const onFetchIntervalChange = (e: ChangeEvent<HTMLSelectElement>) => setFetchIntervalSeconds(Number(e.target.value));
  const onHealthIntervalChange = (e: ChangeEvent<HTMLSelectElement>) => setHealthPollIntervalSeconds(Number(e.target.value));

  const statusTone =
    health?.status === 'healthy'
      ? 'text-terminal-green border-terminal-green/30 bg-terminal-green/10'
      : health?.status === 'degraded'
      ? 'text-yellow-300 border-yellow-300/30 bg-yellow-300/10'
      : 'text-cyber-red border-cyber-red/30 bg-cyber-red/10';

  const healthBadge = healthQuery.isError ? 'OFFLINE' : health?.status?.toUpperCase() ?? '...';

  return (
    <div className="glass-panel overflow-hidden">
      {/* Collapsible header — health badge always visible */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 border-b border-white/5 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={13} className="text-cyber-blue" />
          <span className="data-ink">Runtime Controls</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[9px] font-mono px-1.5 py-0.5 border rounded ${statusTone}`}>
            {healthBadge}
          </span>
          {open ? <ChevronUp size={13} className="text-white/30" /> : <ChevronDown size={13} className="text-white/30" />}
        </div>
      </button>

      {open && (
        <div className="p-4 space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => healthQuery.refetch()}
              className="px-2 py-1 text-[10px] font-mono border border-white/20 rounded hover:bg-white/10 transition-colors flex items-center gap-1"
            >
              <RefreshCcw size={10} />
              REFRESH
            </button>
          </div>

          <div className="space-y-2 text-[11px] font-mono text-white/75">
            <div className="flex items-center justify-between">
              <span>Map Auto-Refresh</span>
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={autoRefreshEnabled} onChange={onAutoRefreshChange} className="accent-cyber-blue" />
                <span className={autoRefreshEnabled ? 'text-terminal-green' : 'text-white/50'}>
                  {autoRefreshEnabled ? 'ON' : 'OFF'}
                </span>
              </label>
            </div>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-white/70"><Timer size={12} /><span>Fetch Interval</span></div>
              <select value={fetchIntervalSeconds} onChange={onFetchIntervalChange} className="bg-surface-900 border border-white/20 rounded px-2 py-1 text-[11px] font-mono">
                {FETCH_INTERVAL_OPTIONS.map((s) => <option key={s} value={s}>{s}s</option>)}
              </select>
            </div>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-white/70"><HeartPulse size={12} /><span>Health Polling</span></div>
              <select value={healthPollIntervalSeconds} onChange={onHealthIntervalChange} className="bg-surface-900 border border-white/20 rounded px-2 py-1 text-[11px] font-mono">
                {HEALTH_INTERVAL_OPTIONS.map((s) => <option key={s} value={s}>{s}s</option>)}
              </select>
            </div>
          </div>

          <div className="space-y-2 border-t border-white/10 pt-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2"><Activity size={12} className="text-cyber-blue" /><span className="data-ink">System Health</span></div>
              <span className={`text-[10px] font-mono uppercase px-2 py-1 border rounded ${statusTone}`}>
                {healthQuery.isError ? 'offline' : health?.status ?? 'loading'}
              </span>
            </div>
            {healthQuery.isError ? (
              <div className="text-[10px] font-mono text-cyber-red/90">Unable to reach backend health endpoint.</div>
            ) : (
              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-white/70">
                <div>API v{health?.version ?? '--'}</div>
                <div>Uptime: {health ? `${Math.round(health.uptime_seconds)}s` : '--'}</div>
                <div>BQ: {health?.bigquery.connected ? 'OK' : 'DOWN'}</div>
                <div>Hot Tier: {health?.hot_tier.available ? 'READY' : 'MISSING'}</div>
                <div className="col-span-2 text-white/55">Total Rows: {health?.hot_tier.total_rows?.toLocaleString() ?? '--'}</div>
                <div className="col-span-2 text-white/55">Last Ingest: {health?.hot_tier.last_updated_at ?? '--'}</div>
                <div className="col-span-2 text-white/55">Parquet files: {health?.hot_tier.parquet_files ?? '--'}</div>
                <div className="col-span-2 text-white/55">Hot/cold cutoff: {health?.hot_tier.cutoff_days ?? '--'} days</div>
                <div className="col-span-2 text-white/55">Filters: {dateRange[0]} to {dateRange[1]}{eventRootCode ? ` | ${eventRootCode}` : ''}</div>
              </div>
            )}
          </div>

          <div className="space-y-2 border-t border-white/10 pt-3">
            <div className="flex items-center justify-between">
              <span className="data-ink">Backend Runtime Settings</span>
              <span className="text-[10px] font-mono text-white/40">
                {settingsQuery.isError ? 'unavailable' : settingsQuery.isLoading ? 'loading' : 'synced'}
              </span>
            </div>
            {settingsQuery.isError ? (
              <div className="text-[10px] font-mono text-cyber-red/90">Runtime settings endpoint unavailable.</div>
            ) : (
              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-white/70">
                <div>Lookback: {settingsQuery.data?.default_lookback_days ?? '--'}d</div>
                <div>Limit: {settingsQuery.data?.default_query_limit ?? '--'}</div>
                <div>Hot cutoff: {settingsQuery.data?.hot_tier_cutoff_days ?? '--'}d</div>
                <div>Cold window: {settingsQuery.data?.cold_tier_max_window_days ?? '--'}d</div>
                <div>Cold quota: {settingsQuery.data?.cold_tier_monthly_query_limit ?? '--'}/mo</div>
                <div>BQ cap: {settingsQuery.data ? `${Math.round(settingsQuery.data.bq_max_scan_bytes / 1_000_000)}MB` : '--'}</div>
                <div className="col-span-2 text-white/55">Realtime: every {settingsQuery.data?.realtime_fetch_interval_minutes ?? '--'} min</div>
                <div className="col-span-2 text-white/55">Cron: daily {settingsQuery.data?.daily_batch_cron_utc ?? '--'} | nightly {settingsQuery.data?.nightly_ai_cron_utc ?? '--'}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};