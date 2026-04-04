/**
 * FILE: frontend/src/components/ambient/SpikeAlertsCard.tsx
 *
 * Activity Spike Alert System (PHASE 4).
 * Polls /analytics/spikes every 5 min.
 * Also displays countries flagged as anomalous from /analytics/anomalies.
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronUp, Zap, AlertCircle, Activity, Globe } from 'lucide-react';

import { apiService } from '../../services/api';
import { useStore } from '../../store/useStore';
import { SpikeAlertEntry } from '../../types';

export const SpikeAlertsCard: React.FC = () => {
  const { setSelectedEvent, setSelectedCountry } = useStore();
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Poll spikes every 5 minutes
  const spikeQuery = useQuery({
    queryKey: ['activity-spikes'],
    queryFn: () => apiService.getActivitySpikes(),
    refetchInterval: 300_000, // 5 minutes
    staleTime: 300_000,
  });

  // Poll anomalies every 5 minutes
  const anomalyQuery = useQuery({
    queryKey: ['anomalies'],
    queryFn: () => apiService.getAnomalies(),
    refetchInterval: 300_000,
    staleTime: 300_000,
  });

  const handleOpenDossier = (countryCode: string) => {
    // Standard event/country selection pattern
    setSelectedEvent(null);
    setSelectedCountry(countryCode);
  };

  const spikes = spikeQuery.data?.data || [];
  const anomalies = anomalyQuery.data?.data || {};
  
  // Identify anomalies that aren't already in spikes to avoid duplicates
  const anomalyOnlyCCs = Object.keys(anomalies).filter(
    cc => anomalies[cc].is_anomaly && !spikes.some(s => s.country_code === cc)
  );

  const hasAlerts = spikes.length > 0 || anomalyOnlyCCs.length > 0;

  // Empty state if no spikes or anomalies
  if (!hasAlerts) {
    return (
      <div className="glass-panel w-full p-3 flex items-center justify-center border-terminal-green/20">
        <span className="text-[10px] font-mono text-terminal-green/50 uppercase tracking-widest">
          No anomalous activity detected
        </span>
      </div>
    );
  }

  return (
    <div className="glass-panel w-full overflow-hidden border-cyber-red/20 flex flex-col">
      {/* Header with toggle */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="
          w-full flex items-center justify-between
          px-4 py-3
          border-b border-white/5
          hover:bg-white/5 transition-colors
          shrink-0
        "
      >
        <div className="flex items-center gap-2">
          <div className="relative">
            <Zap size={13} className="text-cyber-red animate-pulse" />
            <div className="absolute inset-0 bg-cyber-red/20 blur-sm rounded-full animate-ping" />
          </div>
          <span className="data-ink text-cyber-red">
            ACTIVITY SPIKES ({spikes.length + anomalyOnlyCCs.length})
          </span>
        </div>
        {isCollapsed ? (
          <ChevronDown size={13} className="text-white/30" />
        ) : (
          <ChevronUp size={13} className="text-white/30" />
        )}
      </button>

      {/* Body — Scrollable if many alerts */}
      {!isCollapsed && (
        <div className="p-3 space-y-2 max-h-[400px] overflow-y-auto custom-scrollbar">
          {/* Spike Alerts */}
          {spikes.map((s: SpikeAlertEntry) => (
            <div 
              key={s.country_code}
              className="p-2 rounded bg-cyber-red/5 border border-cyber-red/10 flex flex-col gap-1 transition-colors hover:bg-cyber-red/10"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 min-w-0">
                  <Activity size={11} className="text-cyber-red shrink-0" />
                  <span className="text-[11px] font-mono font-bold text-white/90 truncate">
                    {s.country_display || s.country_code}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-cyber-red font-bold shrink-0">
                  {s.spike_ratio}x spike
                </span>
              </div>
              <div className="flex items-center justify-between ml-[17px]">
                <span className="text-[9px] font-mono text-white/40">
                  {s.events_24h} events vs {s.baseline_avg} avg
                </span>
                <button
                  onClick={() => handleOpenDossier(s.country_code)}
                  className="text-[9px] font-mono text-cyber-blue hover:text-white underline transition-colors"
                >
                  [OPEN DOSSIER]
                </button>
              </div>
              {/* Highlight if this spike is also an AI anomaly */}
              {anomalies[s.country_code]?.is_anomaly && (
                <div className="mt-1 flex items-center gap-1.5 ml-[17px]">
                  <AlertCircle size={9} className="text-amber-400 shrink-0" />
                  <span className="text-[8px] font-mono text-amber-400/60 truncate">
                    {anomalies[s.country_code].reason}
                  </span>
                </div>
              )}
            </div>
          ))}

          {/* Anomaly-only entries (AI detected deviation without raw volume spike) */}
          {anomalyOnlyCCs.map((cc) => (
            <div 
              key={cc}
              className="p-2 rounded bg-amber-500/5 border border-amber-500/10 flex flex-col gap-1 transition-colors hover:bg-amber-500/10"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 min-w-0">
                  <Globe size={11} className="text-amber-400 shrink-0" />
                  <span className="text-[11px] font-mono font-bold text-white/90 truncate">
                    {anomalies[cc].country_display || cc}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-amber-400 font-bold uppercase shrink-0">
                  Anomaly
                </span>
              </div>
              <div className="flex items-center justify-between ml-[17px]">
                <span className="text-[9px] font-mono text-amber-400/60 italic truncate max-w-[180px]">
                  {anomalies[cc].reason}
                </span>
                <button
                  onClick={() => handleOpenDossier(cc)}
                  className="text-[9px] font-mono text-cyber-blue hover:text-white underline transition-colors"
                >
                  [OPEN DOSSIER]
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
