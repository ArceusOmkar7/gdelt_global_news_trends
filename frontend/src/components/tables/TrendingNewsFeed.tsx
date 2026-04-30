import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiService } from '../../services/api';
import { useStore } from '../../store/useStore';
import { Clock, Globe, Link2, ExternalLink } from 'lucide-react';

import { Event } from '../../types';

interface TrendingNewsFeedProps {
  category: string;
  eventRootCodes: string[] | null;
  geoFilter: { countryCode: string | null; stateName: string | null; cityName: string | null };
  themeCategory: string | null;
}

export function TrendingNewsFeed({ category, eventRootCodes, geoFilter, themeCategory }: TrendingNewsFeedProps) {
  const { dateRange, setSelectedEvent } = useStore();
  const [limit] = useState(50);

  const { data, isLoading, error } = useQuery({
    queryKey: ['global-events', dateRange[0], dateRange[1], eventRootCodes, geoFilter, themeCategory, limit],
    queryFn: () =>
      apiService.getGlobalEvents(
        dateRange[0],
        dateRange[1],
        eventRootCodes,
        limit,
        geoFilter,
        themeCategory
      ),
    enabled: true,
    staleTime: 60000,
  });

  const events = data?.data || [];

  if (isLoading) {
    return (
      <div className="flex-1 rounded-xl overflow-hidden shadow-lg border border-white/5 glass-panel p-6 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-t-2 border-cyber-blue rounded-full animate-spin" />
          <span className="text-white/50 font-mono text-sm uppercase tracking-widest animate-pulse">
            SCANNING GLOBAL CHANNELS: {category}...
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 rounded-xl overflow-hidden shadow-lg border border-red-500/20 bg-red-500/5 p-6 flex items-center justify-center min-h-[400px]">
        <span className="text-red-400 font-mono text-sm">Failed to retrieve network feed.</span>
      </div>
    );
  }

  if (!events.length) {
    return (
      <div className="flex-1 rounded-xl overflow-hidden shadow-lg border border-white/5 glass-panel p-6 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2">
          <Globe className="text-white/20 w-12 h-12 mb-2" />
          <span className="text-white/50 font-mono text-sm uppercase tracking-widest">
            NO HIGH-CONFIDENCE SIGNALS DETECTED FOR {category}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 rounded-xl overflow-hidden shadow-lg border border-white/5 glass-panel flex flex-col min-h-[600px] h-full">
      {/* Header */}
      <div className="p-4 border-b border-white/5 flex items-center justify-between bg-surface-900/50 shrink-0">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-6 h-6">
            <span className="absolute inline-flex h-full w-full rounded-full bg-cyber-blue opacity-20 animate-ping" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyber-blue" />
          </div>
          <h2 className="font-mono text-sm font-bold tracking-widest uppercase text-white">
            {category} TRENDING INTEL
          </h2>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono text-cyber-blue/70">
          <Globe size={12} />
          <span>{events.length} SIGNALS INTERCEPTED</span>
        </div>
      </div>

      {/* Feed List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2">
        {events.map((event: Event) => {
          // Fallback to sourceUrl domain if possible
          let sourceDomain = 'Unknown Source';
          if (event.source_url) {
            try {
              sourceDomain = new URL(event.source_url).hostname.replace('www.', '');
            } catch {
              // ignore
            }
          }

          return (
            <div
              key={event.global_event_id}
              onClick={() => setSelectedEvent(event)}
              className="p-4 rounded-lg border border-white/5 bg-white/5 hover:bg-white/10 hover:border-cyber-blue/30 transition-all cursor-pointer group flex gap-4"
            >
              {/* Context indicator */}
              <div className="shrink-0 pt-1">
                <div className={`w-2 h-2 rounded-full ${event.goldstein_scale && event.goldstein_scale < 0 ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]' : 'bg-cyber-blue shadow-[0_0_8px_rgba(0,243,255,0.6)]'}`} />
              </div>

              <div className="flex-1 min-w-0">
                {/* Meta row */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[10px] text-cyber-blue px-2 py-0.5 rounded bg-cyber-blue/10 uppercase">
                      {event.action_geo_country_code || 'GLOBAL'}
                    </span>
                    <div className="flex items-center gap-1 text-white/40 text-[10px] font-mono">
                      <Clock size={10} />
                      <span>{event.sql_date}</span>
                    </div>
                  </div>
                  
                  {/* Goldstein/Tone indicator if available */}
                  {(event.goldstein_scale != null || event.avg_tone != null) && (
                    <div className="flex items-center gap-3 text-[10px] font-mono">
                      {event.goldstein_scale != null && (
                        <span className={event.goldstein_scale < 0 ? 'text-red-400' : 'text-emerald-400'}>
                          GS: {event.goldstein_scale > 0 ? '+' : ''}{event.goldstein_scale.toFixed(1)}
                        </span>
                      )}
                      {event.avg_tone != null && (
                        <span className={event.avg_tone < 0 ? 'text-orange-400' : 'text-cyber-blue'}>
                          TN: {event.avg_tone > 0 ? '+' : ''}{event.avg_tone.toFixed(1)}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Title & Source */}
                <div className="flex items-start justify-between gap-4">
                  <h3 className="text-sm font-medium text-white/90 group-hover:text-cyber-blue transition-colors line-clamp-2">
                    {/* Event summary generation based on actors/themes if we don't have titles readily available */}
                    {event.themes && event.themes.length > 0 
                      ? `Signal detected regarding ${event.themes[0].replace(/_/g, ' ')} activity`
                      : `Activity detected in ${event.action_geo_country_code || 'unknown region'}`
                    }
                  </h3>
                  
                  {event.source_url && (
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 p-1.5 rounded bg-white/5 hover:bg-white/20 transition-colors text-white/50 hover:text-white"
                      onClick={(e: React.MouseEvent) => e.stopPropagation()}
                    >
                      <ExternalLink size={14} />
                    </a>
                  )}
                </div>

                <div className="mt-3 flex items-center gap-4">
                  <span className="text-[10px] text-white/40 font-mono flex items-center gap-1 truncate max-w-[200px]">
                    <Link2 size={10} />
                    {sourceDomain}
                  </span>
                  {event.num_mentions > 0 && (
                    <span className="text-[10px] text-white/40 font-mono">
                      {event.num_mentions} MENTIONS
                    </span>
                  )}
                  {event.persons && event.persons.length > 0 && (
                    <div className="flex gap-1 overflow-hidden">
                      {event.persons.slice(0, 2).map((p, i) => (
                        <span key={i} className="text-[9px] bg-white/5 text-white/60 px-1.5 py-0.5 rounded uppercase truncate max-w-[100px]">
                          {p.split(' ')[0]}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
