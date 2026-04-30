import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { useStore } from '../../store/useStore';
import { apiService } from '../../services/api';
import { Activity } from 'lucide-react';

interface EventTrendChartProps {
  eventRootCode?: string | null;
}

function formatYAxis(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CustomTooltip = ({ active, payload, label, isDark }: any) => {
  if (!active || !payload?.length) return null;
  const total    = payload.find((p: { dataKey: string }) => p.dataKey === 'total')?.value ?? 0;
  const conflict = payload.find((p: { dataKey: string }) => p.dataKey === 'conflict')?.value ?? 0;
  const ratio    = total > 0 ? ((conflict / total) * 100).toFixed(1) : '0.0';

  return (
    <div
      className="rounded-lg px-4 py-3 shadow-xl text-xs font-mono space-y-1.5 border"
      style={{
        background: isDark ? 'rgba(10,10,20,0.96)' : 'rgba(255,255,255,0.97)',
        borderColor: isDark ? 'rgba(0,243,255,0.25)' : 'rgba(15,23,42,0.15)',
        color: isDark ? '#e5e7eb' : '#0F172A',
        minWidth: 160,
      }}
    >
      <div className="font-bold tracking-widest uppercase text-[10px] opacity-60 mb-1">{label}</div>
      <div className="flex items-center justify-between gap-6">
        <span style={{ color: '#00f3ff' }}>● Total</span>
        <span className="font-bold">{total.toLocaleString()}</span>
      </div>
      <div className="flex items-center justify-between gap-6">
        <span style={{ color: '#ff4060' }}>● Conflict</span>
        <span className="font-bold">{conflict.toLocaleString()}</span>
      </div>
      <div
        className="mt-1.5 pt-1.5 flex justify-between gap-6 opacity-70"
        style={{ borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)'}` }}
      >
        <span>Conflict ratio</span>
        <span className="font-bold" style={{ color: '#ff4060' }}>{ratio}%</span>
      </div>
    </div>
  );
};

export const EventTrendChart: React.FC<EventTrendChartProps> = ({ eventRootCode }) => {
  const { dateRange, dateWindowReady, isDarkTheme } = useStore();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['daily-trend', dateRange, eventRootCode],
    queryFn: () => apiService.getDailyTrend(dateRange[0], dateRange[1], eventRootCode),
    enabled: dateWindowReady,
    staleTime: 60_000,
  });

  // Chart colour tokens
  const ct = isDarkTheme
    ? {
        axis: 'rgba(255,255,255,0.30)',
        tick: 'rgba(255,255,255,0.45)',
        axLine: 'rgba(255,255,255,0.10)',
        grid: 'rgba(255,255,255,0.04)',
        totalStop0: 'rgba(0,243,255,0.40)',
        totalStop1: 'rgba(0,243,255,0.04)',
        conflictStop0: 'rgba(255,64,96,0.55)',
        conflictStop1: 'rgba(255,64,96,0.08)',
        totalStroke: '#00f3ff',
        conflictStroke: '#ff4060',
        legendText: 'rgba(255,255,255,0.6)',
      }
    : {
        axis: 'rgba(15,23,42,0.30)',
        tick: 'rgba(15,23,42,0.50)',
        axLine: 'rgba(15,23,42,0.10)',
        grid: 'rgba(15,23,42,0.04)',
        totalStop0: 'rgba(3,105,161,0.30)',
        totalStop1: 'rgba(3,105,161,0.04)',
        conflictStop0: 'rgba(220,38,38,0.45)',
        conflictStop1: 'rgba(220,38,38,0.06)',
        totalStroke: '#0369A1',
        conflictStroke: '#DC2626',
        legendText: 'rgba(15,23,42,0.55)',
      };

  return (
    <div className="glass-panel rounded-xl p-5 shadow-lg border-white/5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-cyber-blue" />
          <span className="data-ink text-cyber-blue">Event Volume Trend</span>
        </div>
        <div className="flex items-center gap-4 text-[10px] font-mono">
          <span className="flex items-center gap-1.5" style={{ color: ct.totalStroke }}>
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: ct.totalStroke, opacity: 0.7 }} />
            ALL EVENTS
          </span>
          <span className="flex items-center gap-1.5" style={{ color: ct.conflictStroke }}>
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: ct.conflictStroke, opacity: 0.7 }} />
            CONFLICT
          </span>
        </div>
      </div>

      {/* Chart */}
      <div className="h-[200px]">
        {isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-t-cyber-blue border-transparent rounded-full animate-spin" />
              <span className="text-[10px] font-mono text-white/30 uppercase tracking-widest animate-pulse">
                Computing Trend…
              </span>
            </div>
          </div>
        ) : isError || !data?.data?.length ? (
          <div className="h-full flex items-center justify-center text-[11px] font-mono text-white/30 uppercase">
            No trend data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={ct.totalStop0} stopOpacity={1} />
                  <stop offset="95%" stopColor={ct.totalStop1} stopOpacity={1} />
                </linearGradient>
                <linearGradient id="gradConflict" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={ct.conflictStop0} stopOpacity={1} />
                  <stop offset="95%" stopColor={ct.conflictStop1} stopOpacity={1} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke={ct.grid} vertical={false} />

              <XAxis
                dataKey="date"
                stroke={ct.axis}
                tick={{ fill: ct.tick, fontSize: 9, fontFamily: 'monospace' }}
                tickLine={false}
                axisLine={{ stroke: ct.axLine }}
                tickFormatter={(v: string) => v.slice(5)} // show MM-DD
                interval="preserveStartEnd"
              />
              <YAxis
                stroke={ct.axis}
                tick={{ fill: ct.tick, fontSize: 9, fontFamily: 'monospace' }}
                tickLine={false}
                axisLine={{ stroke: ct.axLine }}
                tickFormatter={formatYAxis}
                width={42}
              />

              <Tooltip
                content={<CustomTooltip isDark={isDarkTheme} />}
                cursor={{ stroke: ct.axis, strokeWidth: 1, strokeDasharray: '4 4' }}
              />

              {/* Outer area: all events */}
              <Area
                type="monotone"
                dataKey="total"
                stroke={ct.totalStroke}
                strokeWidth={2}
                fill="url(#gradTotal)"
                dot={false}
                activeDot={{ r: 4, fill: ct.totalStroke, strokeWidth: 0 }}
              />

              {/* Inner area: conflict events (stacked inside total) */}
              <Area
                type="monotone"
                dataKey="conflict"
                stroke={ct.conflictStroke}
                strokeWidth={1.5}
                fill="url(#gradConflict)"
                dot={false}
                activeDot={{ r: 4, fill: ct.conflictStroke, strokeWidth: 0 }}
              />

              <Legend wrapperStyle={{ display: 'none' }} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default EventTrendChart;
