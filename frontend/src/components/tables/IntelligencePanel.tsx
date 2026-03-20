import React from 'react';
import { useStore } from '../../store/useStore';
import { apiService } from '../../services/api';
import { useMutation, useQuery } from '@tanstack/react-query';
import { 
  X, 
  ExternalLink, 
  Brain, 
  CheckCircle, 
  AlertTriangle,
  Activity,
  User,
  MapPin,
  RefreshCcw,
  Globe,
  Users
} from 'lucide-react';

export const IntelligencePanel: React.FC = () => {
  const { 
    selectedEvent, 
    setSelectedEvent, 
    currentAnalysis, 
    setCurrentAnalysis,
    selectedCountry,
    setSelectedCountry,
    dateRange
  } = useStore();

  const regionalStatsQuery = useQuery({
    queryKey: ['regional-stats', selectedCountry, dateRange],
    queryFn: () => apiService.getRegionalStats(selectedCountry!, dateRange[0], dateRange[1]),
    enabled: !!selectedCountry && !selectedEvent,
  });

  const regionalEventsQuery = useQuery({
    queryKey: ['regional-events', selectedCountry, dateRange],
    queryFn: () => apiService.getEventsByRegion(selectedCountry!, dateRange[0], dateRange[1], 10),
    enabled: !!selectedCountry && !selectedEvent,
  });

  const analyzeMutation = useMutation({
    mutationFn: (eventId: number) => apiService.analyzeEvent(eventId),
    onSuccess: (data) => {
      setCurrentAnalysis(data);
    },
  });

  if (!selectedEvent && !selectedCountry) return null;

  const handleAnalyze = () => {
    if (selectedEvent) {
      analyzeMutation.mutate(selectedEvent.global_event_id);
    }
  };

  const getSentimentColor = (sentiment: string) => {
    if (sentiment === 'Positive') return 'text-terminal-green';
    if (sentiment === 'Negative') return 'text-cyber-red';
    return 'text-cyber-blue';
  };

  return (
    <div className="absolute right-0 top-0 h-full w-[450px] z-50 glass-panel shadow-2xl transition-transform duration-300 animate-in slide-in-from-right flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-white/10 flex justify-between items-center bg-surface-900/50">
        <div>
          <span className="data-ink text-cyber-blue">
            {selectedEvent ? 'Event Intelligence' : `Regional Dossier: ${selectedCountry}`}
          </span>
          <h2 className="text-xl font-bold font-mono glowing-text mt-1 uppercase">
            {selectedEvent ? `EID-${selectedEvent.global_event_id}` : 'Sector Analysis'}
          </h2>
        </div>
        <button 
          onClick={() => {
            if (selectedEvent) {
              setSelectedEvent(null);
            } else {
              setSelectedCountry(null);
            }
          }}
          className="p-2 hover:bg-white/10 rounded transition-colors text-white/50 hover:text-white"
        >
          <X size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
        {selectedEvent ? (
          <>
            {/* Core Metrics */}
            <section className="grid grid-cols-2 gap-4">
              <div className="bg-surface-900/40 p-3 rounded panel-border">
                <span className="data-ink">Goldstein</span>
                <div className={`text-xl font-bold font-mono mt-1 ${
                  selectedEvent.goldstein_scale && selectedEvent.goldstein_scale < 0 ? 'text-cyber-red' : 'text-terminal-green'
                }`}>
                  {selectedEvent.goldstein_scale?.toFixed(1) || '0.0'}
                </div>
              </div>
              <div className="bg-surface-900/40 p-3 rounded panel-border">
                <span className="data-ink">Tone</span>
                <div className={`text-xl font-bold font-mono mt-1 ${
                  selectedEvent.avg_tone && selectedEvent.avg_tone < 0 ? 'text-cyber-red' : 'text-terminal-green'
                }`}>
                  {selectedEvent.avg_tone?.toFixed(1) || '0.0'}
                </div>
              </div>
              <div className="bg-surface-900/40 p-3 rounded panel-border">
                <span className="data-ink">Mentions</span>
                <div className="text-xl font-bold font-mono mt-1 text-white">
                  {selectedEvent.num_mentions}
                </div>
              </div>
              <div className="bg-surface-900/40 p-3 rounded panel-border">
                <span className="data-ink">Sources</span>
                <div className="text-xl font-bold font-mono mt-1 text-white">
                  {selectedEvent.num_sources || 0}
                </div>
              </div>
            </section>

            {/* Location & Date */}
            <section className="space-y-4">
              <div className="flex items-start gap-3">
                <MapPin size={18} className="text-cyber-blue mt-0.5" />
                <div>
                  <span className="data-ink">Geography</span>
                  <div className="text-sm font-mono mt-1">
                    LAT: {selectedEvent.lat?.toFixed(4)}<br/>
                    LON: {selectedEvent.lon?.toFixed(4)}
                  </div>
                </div>
              </div>
              
              <div className="flex items-start gap-3">
                <Activity size={18} className="text-cyber-blue mt-0.5" />
                <div>
                  <span className="data-ink">CAMEO Root Code</span>
                  <div className="text-sm font-mono mt-1">
                    {selectedEvent.event_root_code || 'UNSPECIFIED'}
                  </div>
                </div>
              </div>
            </section>

            {/* Actors */}
            <section className="bg-surface-700/30 p-4 rounded panel-border space-y-4">
              <div className="flex items-center gap-2">
                <User size={16} className="text-cyber-blue" />
                <span className="data-ink">Key Actors</span>
              </div>
              <div className="grid grid-cols-1 gap-3">
                {(selectedEvent.actor1_country_code || selectedEvent.actor1_type) && (
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-white/40 uppercase font-mono">Actor 1</span>
                    <div className="flex gap-2">
                      {selectedEvent.actor1_country_code && (
                        <span className="px-2 py-1 bg-surface-900/60 rounded text-xs font-mono panel-border">
                          {selectedEvent.actor1_country_code}
                        </span>
                      )}
                      {selectedEvent.actor1_type && (
                        <span className="px-2 py-1 bg-cyber-blue/10 text-cyber-blue rounded text-xs font-mono border border-cyber-blue/20">
                          {selectedEvent.actor1_type}
                        </span>
                      )}
                    </div>
                  </div>
                )}
                {(selectedEvent.actor2_country_code || selectedEvent.actor2_type) && (
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-white/40 uppercase font-mono">Actor 2</span>
                    <div className="flex gap-2">
                      {selectedEvent.actor2_country_code && (
                        <span className="px-2 py-1 bg-surface-900/60 rounded text-xs font-mono panel-border">
                          {selectedEvent.actor2_country_code}
                        </span>
                      )}
                      {selectedEvent.actor2_type && (
                        <span className="px-2 py-1 bg-cyber-blue/10 text-cyber-blue rounded text-xs font-mono border border-cyber-blue/20">
                          {selectedEvent.actor2_type}
                        </span>
                      )}
                    </div>
                  </div>
                )}
                {!selectedEvent.actor1_country_code && !selectedEvent.actor2_country_code && !selectedEvent.actor1_type && (
                  <span className="text-white/30 text-xs font-mono">Anonymous Actors</span>
                )}
              </div>
            </section>

            {/* Knowledge Graph Insights */}
            {(Array.isArray(selectedEvent.themes) && selectedEvent.themes.length > 0 || Array.isArray(selectedEvent.persons) && selectedEvent.persons.length > 0 || Array.isArray(selectedEvent.organizations) && selectedEvent.organizations.length > 0) && (
              <section className="space-y-4 pt-4 border-t border-white/5">
                <div className="flex items-center gap-2">
                  <Globe size={16} className="text-terminal-green" />
                  <span className="data-ink text-terminal-green">Knowledge Graph Insights</span>
                </div>
                
                <div className="space-y-4">
                  {Array.isArray(selectedEvent.themes) && selectedEvent.themes.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[10px] text-white/40 uppercase font-mono">Top Themes</span>
                      <div className="flex flex-wrap gap-1">
                        {selectedEvent.themes.slice(0, 12).map((theme, i) => (
                          <span key={i} className="px-2 py-0.5 bg-surface-900/40 rounded text-[10px] font-mono text-white/80 border border-white/5">
                            {theme}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    {Array.isArray(selectedEvent.persons) && selectedEvent.persons.length > 0 && (
                      <div className="space-y-2">
                        <span className="text-[10px] text-white/40 uppercase font-mono">People</span>
                        <div className="flex flex-col gap-1">
                          {selectedEvent.persons.slice(0, 5).map((person, i) => (
                            <span key={i} className="text-[11px] font-mono text-cyber-blue truncate">
                              {person}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {Array.isArray(selectedEvent.organizations) && selectedEvent.organizations.length > 0 && (
                      <div className="space-y-2">
                        <span className="text-[10px] text-white/40 uppercase font-mono">Organizations</span>
                        <div className="flex flex-col gap-1">
                          {selectedEvent.organizations.slice(0, 5).map((org, i) => (
                            <span key={i} className="text-[11px] font-mono text-amber-500 truncate">
                              {org}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </section>
            )}

            {/* LLM Analysis Section */}
            <section className="pt-4 border-t border-white/5">
              {!currentAnalysis && !analyzeMutation.isPending && !analyzeMutation.isError ? (
                <button 
                  onClick={handleAnalyze}
                  className="w-full py-4 bg-cyber-blue hover:bg-cyber-blue/90 text-surface-900 font-bold font-mono flex items-center justify-center gap-2 transition-all group"
                >
                  <Brain size={20} className="group-hover:animate-pulse" />
                  ANALYZE SOURCE VIA LLM
                </button>
              ) : analyzeMutation.isPending ? (
                <div className="w-full p-8 border border-cyber-blue/20 bg-cyber-blue/5 flex flex-col items-center justify-center gap-4 text-center">
                  <div className="w-10 h-10 border-2 border-t-cyber-blue border-transparent rounded-full animate-spin" />
                  <div className="space-y-1">
                    <div className="text-cyber-blue font-bold font-mono">COGNITIVE PROCESSING</div>
                    <div className="text-[10px] text-cyber-blue/60 font-mono animate-pulse">EXTRACTING SEMANTIC VECTORS...</div>
                  </div>
                </div>
              ) : analyzeMutation.isError ? (
                <div className="w-full p-6 border border-cyber-red/30 bg-cyber-red/5 space-y-4 rounded">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={18} className="text-cyber-red" />
                    <span className="data-ink text-cyber-red">Analysis Failed</span>
                  </div>
                  <p className="text-[11px] text-white/60 font-mono uppercase leading-tight">
                    {analyzeMutation.error instanceof Error ? analyzeMutation.error.message : 'Uplink synchronization error detected in neural net.'}
                  </p>
                  <button 
                    onClick={handleAnalyze}
                    className="w-full py-2 bg-cyber-red/20 hover:bg-cyber-red/30 border border-cyber-red/50 text-cyber-red font-mono text-[10px] flex items-center justify-center gap-2 transition-all"
                  >
                    <RefreshCcw size={12} />
                    RETRY UPLINK
                  </button>
                </div>
              ) : (
                <div className="space-y-6 animate-in fade-in duration-1000">
                  <div className="p-4 bg-terminal-green/5 border border-terminal-green/20 rounded-md">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle size={16} className="text-terminal-green" />
                      <span className="data-ink text-terminal-green">Analysis Success</span>
                    </div>
                    <p className="text-sm text-white/90 leading-relaxed font-sans italic">
                      "{currentAnalysis?.summary}"
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <span className="data-ink">Sentiment</span>
                      <div className={`text-sm font-bold font-mono ${getSentimentColor(currentAnalysis?.sentiment || '')}`}>
                        {currentAnalysis?.sentiment}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <span className="data-ink">Confidence</span>
                      <div className="text-sm font-bold font-mono text-white">
                        {((currentAnalysis?.confidence || 0) * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="space-y-2">
                      <span className="data-ink">Entities Detected</span>
                      <div className="flex flex-wrap gap-1">
                        {currentAnalysis?.entities.map((e, i) => (
                          <span key={i} className="text-[10px] bg-white/5 px-2 py-0.5 rounded text-white/70 border border-white/5">
                            {e}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-2">
                      <span className="data-ink">Intelligence Themes</span>
                      <div className="flex flex-wrap gap-1">
                        {currentAnalysis?.themes.map((t, i) => (
                          <span key={i} className="text-[10px] text-cyber-blue border border-cyber-blue/20 px-2 py-0.5 rounded bg-cyber-blue/5">
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </section>
          </>
        ) : (
          /* Regional Dossier UI */
          <div className="space-y-8">
            {regionalStatsQuery.isLoading ? (
              <div className="flex flex-col items-center justify-center h-64 space-y-4">
                <RefreshCcw className="animate-spin text-cyber-blue" size={32} />
                <span className="data-ink text-cyber-blue animate-pulse uppercase tracking-widest">Decrypting Sector Data...</span>
              </div>
            ) : regionalStatsQuery.data ? (
              <>
                <section className="space-y-4">
                  <div className="flex items-center gap-2">
                    <Globe size={16} className="text-terminal-green" />
                    <span className="data-ink text-terminal-green uppercase tracking-wider text-xs">Top Regional Themes</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {regionalStatsQuery.data.top_themes.map((t: any, i: number) => (
                      <div key={i} className="px-2 py-1 bg-surface-800/60 rounded border border-white/5 flex items-center gap-2">
                        <span className="text-[10px] font-mono text-white/90">{t.name}</span>
                        <span className="text-[9px] font-mono text-terminal-green bg-terminal-green/10 px-1 rounded">{t.count}</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="space-y-4 pt-4 border-t border-white/5">
                  <div className="flex items-center gap-2">
                    <User size={16} className="text-cyber-blue" />
                    <span className="data-ink text-cyber-blue uppercase tracking-wider text-xs">Key Entities (People)</span>
                  </div>
                  <div className="grid grid-cols-1 gap-1.5">
                    {regionalStatsQuery.data.top_persons.map((p: any, i: number) => (
                      <div key={i} className="flex justify-between items-center p-2 bg-surface-800/40 rounded border border-white/5">
                        <span className="text-[11px] font-mono text-cyber-blue truncate max-w-[200px]">{p.name}</span>
                        <span className="text-[10px] font-mono text-white/40">{p.count} refs</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="space-y-4 pt-4 border-t border-white/5">
                  <div className="flex items-center gap-2">
                    <Users size={16} className="text-terminal-green" />
                    <span className="data-ink text-terminal-green uppercase tracking-wider text-xs">Active Organizations</span>
                  </div>
                  <div className="grid grid-cols-1 gap-1.5">
                    {regionalStatsQuery.data.top_organizations.map((o: any, i: number) => (
                      <div key={i} className="flex justify-between items-center p-2 bg-surface-800/40 rounded border border-white/5">
                        <span className="text-[11px] font-mono text-terminal-green truncate max-w-[200px]">{o.name}</span>
                        <span className="text-[10px] font-mono text-white/40">{o.count} refs</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="space-y-4 pt-4 border-t border-white/5">
                  <div className="flex items-center gap-2">
                    <Activity size={16} className="text-cyber-blue" />
                    <span className="data-ink text-cyber-blue uppercase tracking-wider text-xs">Top Events in Sector</span>
                  </div>
                  <div className="space-y-2">
                    {regionalEventsQuery.isLoading ? (
                      <div className="text-[10px] font-mono text-white/30 animate-pulse uppercase">Scanning for local signals...</div>
                    ) : regionalEventsQuery.data?.data && regionalEventsQuery.data.data.length > 0 ? (
                      regionalEventsQuery.data.data.map((event: any, i: number) => (
                        <button
                          key={i}
                          onClick={() => setSelectedEvent(event)}
                          className="w-full text-left p-3 bg-surface-800/40 hover:bg-cyber-blue/5 border border-white/5 hover:border-cyber-blue/30 rounded transition-all group"
                        >
                          <div className="flex justify-between items-start mb-1">
                            <span className="text-[10px] font-mono text-cyber-blue group-hover:text-cyber-blue">EID-{event.global_event_id}</span>
                            <span className={`text-[9px] font-mono px-1 rounded ${
                              (event.goldstein_scale || 0) < 0 ? 'text-cyber-red bg-cyber-red/10' : 'text-terminal-green bg-terminal-green/10'
                            }`}>
                              GS: {event.goldstein_scale?.toFixed(1) || '0.0'}
                            </span>
                          </div>
                          <div className="text-[11px] font-mono text-white/70 line-clamp-1 group-hover:text-white/90">
                            {event.event_root_code || 'EVENT'} — {event.source_url ? new URL(event.source_url).hostname : 'Unknown Source'}
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="text-[10px] font-mono text-white/30 uppercase">No individual events found in local buffer.</div>
                    )}
                  </div>
                </section>
              </>
            ) : (
              <div className="p-4 bg-cyber-red/10 border border-cyber-red/30 rounded text-cyber-red text-[10px] font-mono uppercase">
                Failed to retrieve regional dossier. Signal lost.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 bg-surface-900/80 border-t border-white/10">
        {selectedEvent ? (
          <a 
            href={selectedEvent.source_url || '#'} 
            target="_blank" 
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 text-white/40 hover:text-white transition-colors text-xs font-mono"
          >
            <ExternalLink size={14} />
            VIEW RAW SOURCE DATA
          </a>
        ) : (
          <div className="text-center">
            <span className="text-[10px] font-mono text-white/30 uppercase tracking-[0.2em]">Deep Scan Available for Individual Events Only</span>
          </div>
        )}
      </div>
    </div>
  );
};
