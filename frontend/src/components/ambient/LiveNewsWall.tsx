import { useMemo, useRef } from 'react';
import { PlayCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

import { useStore } from '../../store/useStore';
import { apiService } from '../../services/api';
import type { LiveStreamChannel } from '../../types';

function buildLiveEmbedUrl(embedUrl: string): string {
  const params = new URLSearchParams({
    autoplay: '1',
    mute: '1',
    playsinline: '1',
    controls: '0',
    rel: '0',
    modestbranding: '1',
  });
  return `${embedUrl}?${params.toString()}`;
}

function buildChannelLink(channelId: string): string {
  return `https://www.youtube.com/channel/${channelId}/live`;
}

export const LiveNewsWall = () => {
  const { geoFilter } = useStore();
  const refreshAttemptsRef = useRef<Set<string>>(new Set());

  const liveQuery = useQuery({
    queryKey: ['live-streams', geoFilter.countryCode],
    queryFn: () => apiService.getLiveStreams(geoFilter.countryCode),
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
  });

  const groupKey = liveQuery.data?.group_key || 'GLOBAL';
  const groupLabel = liveQuery.data?.label || 'GLOBAL';
  const channels = liveQuery.data?.channels || [];

  const hero = useMemo(() => channels[0], [channels]);
  const secondary = useMemo(() => channels.slice(1, 4), [channels]);

  const handleEmbedError = async (channel: LiveStreamChannel) => {
    if (!channel?.id) return;
    if (refreshAttemptsRef.current.has(channel.id)) return;
    refreshAttemptsRef.current.add(channel.id);
    try {
      await apiService.refreshLiveStream(channel.id);
      await liveQuery.refetch();
    } catch {
      // Keep the fallback state if refresh fails.
    }
  };

  return (
    <section className="glass-panel rounded-xl border border-white/10 shadow-lg p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <PlayCircle size={16} className="text-cyber-blue" />
          <span className="data-ink text-cyber-blue">Live News Streams</span>
        </div>
        <span className="text-[10px] font-mono uppercase tracking-widest text-white/50">
          {groupLabel}
        </span>
      </div>

      {liveQuery.isLoading ? (
        <div className="text-[11px] font-mono text-white/40">Loading live streams...</div>
      ) : liveQuery.isError ? (
        <div className="text-[11px] font-mono text-cyber-red">Failed to load live streams.</div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-[1.6fr_1fr] lg:grid-rows-3">
          {hero && (
            <div
              key={`${groupKey}-${hero.id}`}
              className="rounded-lg overflow-hidden border border-white/10 bg-surface-900/40 flex flex-col lg:row-span-3"
            >
              <div className="aspect-video lg:aspect-auto lg:flex-1">
                {hero.embed_url ? (
                  <iframe
                    src={buildLiveEmbedUrl(hero.embed_url)}
                    title={`${hero.name} live stream`}
                    className="h-full w-full"
                    loading="lazy"
                    allow="autoplay; encrypted-media; picture-in-picture"
                    referrerPolicy="strict-origin-when-cross-origin"
                    sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
                    allowFullScreen
                    onError={() => handleEmbedError(hero)}
                  />
                ) : (
                  <div className="h-full w-full flex items-center justify-center text-[11px] font-mono text-white/40">
                    Live stream unavailable
                  </div>
                )}
              </div>
              <div className="px-3 py-2 border-t border-white/10 flex items-center justify-between gap-2">
                <span className="text-[10px] font-mono text-white/60 truncate">{hero.name}</span>
                <a
                  href={buildChannelLink(hero.id)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[10px] font-mono text-cyber-blue hover:text-cyber-blue/80 whitespace-nowrap"
                >
                  Open
                </a>
              </div>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 lg:row-span-3">
            {secondary.map((channel: LiveStreamChannel) => (
              <div
                key={`${groupKey}-${channel.id}`}
                className="rounded-lg overflow-hidden border border-white/10 bg-surface-900/40"
              >
                <div className="aspect-video">
                  {channel.embed_url ? (
                    <iframe
                      src={buildLiveEmbedUrl(channel.embed_url)}
                      title={`${channel.name} live stream`}
                      className="h-full w-full"
                      loading="lazy"
                      allow="autoplay; encrypted-media; picture-in-picture"
                      referrerPolicy="strict-origin-when-cross-origin"
                      sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
                      allowFullScreen
                      onError={() => handleEmbedError(channel)}
                    />
                  ) : (
                    <div className="h-full w-full flex items-center justify-center text-[11px] font-mono text-white/40">
                      Live stream unavailable
                    </div>
                  )}
                </div>
                <div className="px-3 py-2 border-t border-white/10 flex items-center justify-between gap-2">
                  <span className="text-[10px] font-mono text-white/60 truncate">{channel.name}</span>
                  <a
                    href={buildChannelLink(channel.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[10px] font-mono text-cyber-blue hover:text-cyber-blue/80 whitespace-nowrap"
                  >
                    Open
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
