/**
 * FILE: frontend/src/components/ambient/TopThreatCard.tsx
 *
 * Collapsible glass-panel card shown in the left sidebar (below Mission Parameters).
 * Fetches from /events/top-threat-countries every 2 min.
 * Each row shows country code + colored 0-100 score bar + numeric score.
 * Clicking a row calls setSelectedCountry() to open the Regional Dossier.
 */

import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronUp, ShieldAlert } from 'lucide-react';

import { apiService } from '../../services/api';
import { useStore } from '../../store/useStore';
import type { ThreatCountryEntry } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreColor(score: number): string {
  if (score > 60) return 'text-cyber-red';
  if (score > 30) return 'text-yellow-400';
  return 'text-terminal-green';
}

function barColor(score: number): string {
  if (score > 60) return 'bg-cyber-red';
  if (score > 30) return 'bg-yellow-400';
  return 'bg-terminal-green';
}

function barGlow(score: number): string {
  if (score > 60) return 'shadow-[0_0_6px_rgba(255,0,60,0.6)]';
  if (score > 30) return 'shadow-[0_0_6px_rgba(255,220,0,0.4)]';
  return 'shadow-[0_0_6px_rgba(0,255,65,0.4)]';
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const ThreatRow = ({
  entry,
  rank,
  onClick,
}: {
  entry: ThreatCountryEntry;
  rank: number;
  onClick: () => void;
}) => {
  const pct = Math.min(100, Math.max(0, entry.score));
  return (
    <button
      onClick={onClick}
      className="
        w-full group text-left
        p-2 rounded
        bg-surface-900/40 hover:bg-surface-700/60
        border border-white/5 hover:border-white/15
        transition-all duration-150
      "
    >
      <div className="flex items-center gap-2 mb-1.5">
        {/* Rank badge */}
        <span className="text-[9px] font-mono text-white/25 w-4 shrink-0">
          #{rank}
        </span>
        {/* Country code / name */}
        <span className="text-[11px] font-mono font-bold text-white/80 group-hover:text-white transition-colors flex-1 truncate">
          {entry.country_display || entry.country_code}
        </span>
        {/* Score number */}
        <span className={`text-[11px] font-mono font-bold ${scoreColor(entry.score)} shrink-0`}>
          {entry.score}
        </span>
      </div>

      {/* Score bar */}
      <div className="ml-6 h-1 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor(entry.score)} ${barGlow(entry.score)}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Sub-metrics */}
      <div className="ml-6 mt-1 flex gap-3">
        <span className="text-[9px] font-mono text-white/30">
          {(entry.conflict_ratio * 100).toFixed(0)}% conflict
        </span>
        <span className="text-[9px] font-mono text-white/20">
          {entry.total_events.toLocaleString()} events
        </span>
      </div>
    </button>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const TopThreatCard = () => {
  const {
    threatCardCollapsed,
    setThreatCardCollapsed,
    setSelectedEvent,
    setSelectedCountry,
    dateRange,
  } = useStore();

  const threatQuery = useQuery({
    queryKey: ['top-threat-countries', dateRange[0], dateRange[1]],
    queryFn: () =>
      apiService.getTopThreatCountries(5, dateRange[0], dateRange[1]),
    staleTime: 120_000,
    refetchInterval: 120_000,
    retry: 1,
  });

  const handleRowClick = (countryCode: string) => {
    // Critical ordering rule from CONTEXT.md §7:
    // setSelectedEvent(null) must come BEFORE setSelectedCountry()
    setSelectedEvent(null);
    setSelectedCountry(countryCode);
  };

  return (
    <div className="glass-panel w-full overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setThreatCardCollapsed(!threatCardCollapsed)}
        className="
          w-full flex items-center justify-between
          px-4 py-3
          border-b border-white/5
          hover:bg-white/5 transition-colors
        "
      >
        <div className="flex items-center gap-2">
          <ShieldAlert size={13} className="text-cyber-red" />
          <span className="data-ink">Threat Monitor</span>
        </div>
        <div className="flex items-center gap-2">
          {!threatCardCollapsed && (
            <span className="text-[9px] font-mono text-white/20 uppercase">
              7d
            </span>
          )}
          {threatCardCollapsed ? (
            <ChevronDown size={13} className="text-white/30" />
          ) : (
            <ChevronUp size={13} className="text-white/30" />
          )}
        </div>
      </button>

      {/* Body */}
      {!threatCardCollapsed && (
        <div className="p-3 space-y-1.5">
          {threatQuery.isLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="h-10 bg-white/5 rounded animate-pulse"
                />
              ))}
            </div>
          ) : threatQuery.isError ? (
            <div className="text-[10px] font-mono text-cyber-red/70 uppercase py-2">
              Signal lost — threat data unavailable
            </div>
          ) : threatQuery.data?.data && threatQuery.data.data.length > 0 ? (
            <>
              {threatQuery.data.data.map((entry, i) => (
                <ThreatRow
                  key={entry.country_code}
                  entry={entry}
                  rank={i + 1}
                  onClick={() => handleRowClick(entry.country_code)}
                />
              ))}
              <div className="pt-1 text-[9px] font-mono text-white/15 uppercase tracking-widest text-center">
                Click to open regional dossier
              </div>
            </>
          ) : (
            <div className="text-[10px] font-mono text-white/30 uppercase py-2">
              No data in range
            </div>
          )}
        </div>
      )}
    </div>
  );
};