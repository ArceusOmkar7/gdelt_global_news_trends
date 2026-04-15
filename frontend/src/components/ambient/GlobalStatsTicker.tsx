/**
 * FILE: frontend/src/components/ambient/GlobalStatsTicker.tsx
 *
 * Fixed bottom bar — cycles through live global aggregates.
 * Fetches from /events/global-pulse every 60 s.
 * Collapsible via a chevron toggle (state persisted in Zustand).
 */

import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronUp, Radio } from 'lucide-react';

import { apiService } from '../../services/api';
import { useStore } from '../../store/useStore';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtTone(tone: number | null | undefined): string {
  if (tone == null) return 'N/A';
  return tone.toFixed(2);
}

function fmtRatio(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

function fmtCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function getToneDescriptor(tone: number | null): string {
  if (tone === null) return '';
  if (tone > 0) return '(Cooperative)';
  if (tone >= -1) return '(Neutral)';
  if (tone >= -3) return '(Mildly Hostile)';
  if (tone >= -6) return '(Hostile)';
  return '(Severely Hostile)';
}

// ---------------------------------------------------------------------------
// Ticker items
// ---------------------------------------------------------------------------

interface TickerItem {
  label: string;
  value: string;
  highlight?: boolean; // renders in cyber-red when true
}

function buildItems(data: {
  total_events_today: number;
  most_active_country: string | null;
  most_active_display?: string | null;
  most_active_count: number;
  most_hostile_country: string | null;
  most_hostile_display?: string | null;
  avg_global_tone: number | null;
  global_conflict_ratio: number;
}): TickerItem[] {
  return [
    { label: 'EVENTS TODAY', value: fmtCount(data.total_events_today) },
    {
      label: 'MOST ACTIVE',
      value: data.most_active_display
        ? `${data.most_active_display} (${fmtCount(data.most_active_count)})`
        : data.most_active_country
        ? `${data.most_active_country} (${fmtCount(data.most_active_count)})`
        : 'N/A',
    },
    {
      label: 'MOST HOSTILE',
      value: data.most_hostile_display ?? data.most_hostile_country ?? 'N/A',
      highlight: !!data.most_hostile_country,
    },
    {
      label: 'AVG GLOBAL TONE',
      value: `${fmtTone(data.avg_global_tone)} ${getToneDescriptor(data.avg_global_tone)}`,
    },
    {
      label: 'CONFLICT RATIO',
      value: fmtRatio(data.global_conflict_ratio),
      highlight: data.global_conflict_ratio > 0.35,
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const GlobalStatsTicker = () => {
  const { tickerCollapsed, setTickerCollapsed, dateRange, dateWindowReady } = useStore();
  const [activeIdx, setActiveIdx] = useState(0);
  const cycleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pulseQuery = useQuery({
    queryKey: ['global-pulse', dateRange[0], dateRange[1]],
    queryFn: () => apiService.getGlobalPulse(dateRange[0], dateRange[1]),
    enabled: dateWindowReady,
    staleTime: 60_000,
    refetchInterval: 60_000,
    retry: 1,
  });

  const items = pulseQuery.data ? buildItems(pulseQuery.data) : [];

  // Cycle through items every 3 s when visible
  useEffect(() => {
    if (tickerCollapsed || items.length === 0) return;
    cycleRef.current = setInterval(() => {
      setActiveIdx((i) => (i + 1) % items.length);
    }, 3000);
    return () => {
      if (cycleRef.current) clearInterval(cycleRef.current);
    };
  }, [tickerCollapsed, items.length]);

  return (
    <div
      className="
        fixed bottom-0 left-0 right-0 z-50
        bg-surface-800/95 backdrop-blur-md border-t border-white/10
        font-mono
      "
    >
      {/* Collapsed state — just show the chevron toggle */}
      {tickerCollapsed ? (
        <div className="flex items-center justify-between px-4 py-1">
          <div className="flex items-center gap-2">
            <Radio size={11} className="text-cyber-blue animate-pulse" />
            <span className="text-[9px] text-cyber-blue uppercase tracking-[0.2em]">
              Global Pulse — Collapsed
            </span>
          </div>
          <button
            onClick={() => setTickerCollapsed(false)}
            className="text-white/30 hover:text-white transition-colors"
            aria-label="Expand global stats ticker"
          >
            <ChevronUp size={14} />
          </button>
        </div>
      ) : (
        <div className="flex items-center h-8 px-4 gap-0">
          {/* Live indicator */}
          <div className="flex items-center gap-2 pr-4 border-r border-white/10 shrink-0">
            <Radio size={11} className="text-cyber-blue animate-pulse" />
            <span className="text-[9px] text-cyber-blue uppercase tracking-[0.2em]">
              Live
            </span>
          </div>

          {/* Items — desktop: all visible separated by · ; mobile: cycle */}
          {pulseQuery.isLoading ? (
            <span className="text-[10px] text-white/30 uppercase pl-4 animate-pulse">
              Acquiring signal...
            </span>
          ) : pulseQuery.isError ? (
            <span className="text-[10px] text-cyber-red/70 uppercase pl-4">
              Pulse unavailable
            </span>
          ) : (
            <>
              {/* Wide layout: show all items inline */}
              <div className="hidden md:flex items-center gap-0 flex-1 pl-4 overflow-hidden">
                {items.map((item, i) => (
                  <span key={i} className="flex items-center shrink-0">
                    {i > 0 && (
                      <span className="text-white/20 mx-3 select-none">·</span>
                    )}
                    <span className="text-[9px] text-white/40 uppercase tracking-widest mr-1.5">
                      {item.label}
                    </span>
                    <span
                      className={`text-[10px] font-bold ${
                        item.highlight ? 'text-cyber-red' : 'text-cyber-blue'
                      }`}
                    >
                      {item.value}
                    </span>
                  </span>
                ))}
              </div>

              {/* Narrow layout: cycle */}
              <div className="flex md:hidden items-center flex-1 pl-4">
                {items[activeIdx] && (
                  <span className="flex items-center gap-1.5 transition-all">
                    <span className="text-[9px] text-white/40 uppercase tracking-widest">
                      {items[activeIdx].label}
                    </span>
                    <span
                      className={`text-[10px] font-bold ${
                        items[activeIdx].highlight
                          ? 'text-cyber-red'
                          : 'text-cyber-blue'
                      }`}
                    >
                      {items[activeIdx].value}
                    </span>
                  </span>
                )}
              </div>
            </>
          )}

          {/* Collapse toggle */}
          <button
            onClick={() => setTickerCollapsed(true)}
            className="ml-auto text-white/30 hover:text-white transition-colors shrink-0"
            aria-label="Collapse global stats ticker"
          >
            <ChevronDown size={14} />
          </button>
        </div>
      )}
    </div>
  );
};