import React, { useState, useMemo, useEffect } from 'react';
import Map, { useControl } from 'react-map-gl/mapbox';
import { MapboxOverlay } from '@deck.gl/mapbox';
import type { MapboxOverlayProps } from '@deck.gl/mapbox';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { useQuery } from '@tanstack/react-query';
import { WebMercatorViewport } from '@math.gl/web-mercator';
import { useStore } from '../../store/useStore';
import { apiService } from '../../services/api';
import type { MapAggregation, Event } from '../../types';

const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

// Helper to use DeckGL with react-map-gl
function DeckGLOverlay(props: MapboxOverlayProps & { getCursor?: (info: any) => string }) {
  const overlay = useMemo(() => new MapboxOverlay(props), []);
  useControl(() => overlay);
  overlay.setProps(props);
  return null;
}

export const GlobalEventMap: React.FC = () => {
  const { 
    viewState, 
    setViewState, 
    dateRange, 
    eventRootCode,
    setSelectedEvent,
    selectedEventId
  } = useStore();

  const [mapBBox, setMapBBox] = useState({ n: 90, s: -90, e: 180, w: -180 });

  // Update BBOX when viewState changes
  useEffect(() => {
    const timer = setTimeout(() => {
      const viewport = new WebMercatorViewport({
        ...viewState,
        width: window.innerWidth,
        height: window.innerHeight
      });
      const bounds: any = viewport.getBounds();
      setMapBBox({ 
        w: bounds[0], 
        s: bounds[1], 
        e: bounds[2], 
        n: bounds[3] 
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [viewState]);

  const { data: mapResponse, isLoading } = useQuery({
    queryKey: ['map-data', mapBBox, Math.round(viewState.zoom), dateRange, eventRootCode],
    queryFn: () => apiService.getMapData(
      mapBBox,
      viewState.zoom,
      dateRange[0],
      dateRange[1],
      eventRootCode
    ),
    placeholderData: (previousData) => previousData,
    staleTime: 1000 * 30,
  });

  const layers = useMemo(() => {
    if (!mapResponse) return [];

    if (mapResponse.is_aggregated) {
      return [
        new HeatmapLayer({
          id: 'heatmap',
          data: mapResponse.data as MapAggregation[],
          getPosition: (d: MapAggregation) => [d.lon, d.lat],
          getWeight: (d: MapAggregation) => d.intensity,
          radiusPixels: 25,
          intensity: 1,
          threshold: 0.05,
          colorRange: [
            [0, 243, 255, 50],
            [0, 243, 255, 100],
            [0, 243, 255, 150],
            [0, 243, 255, 200],
            [0, 243, 255, 255],
          ],
        }),
      ];
    } else {
      return [
        new ScatterplotLayer({
          id: 'events',
          data: mapResponse.data as Event[],
          getPosition: (d: Event) => [d.lon, d.lat],
          getFillColor: (d: Event) => {
            const goldstein = d.goldstein_scale || 0;
            if (goldstein < -2) return [255, 0, 60];
            if (goldstein > 2) return [0, 255, 65];
            return [0, 243, 255];
          },
          getRadius: (d: Event) => Math.max(5, d.num_mentions / 5),
          radiusMinPixels: 3,
          radiusMaxPixels: 20,
          pickable: true,
          onClick: ({ object }) => {
            if (object) setSelectedEvent(object);
          },
          stroked: true,
          lineWidthMinPixels: 1,
          getLineColor: (d: Event) => d.global_event_id === selectedEventId ? [255, 255, 255] : [0, 0, 0, 0],
          updateTriggers: {
            getLineColor: [selectedEventId]
          }
        }),
      ];
    }
  }, [mapResponse, selectedEventId, setSelectedEvent]);

  return (
    <div className="relative w-full h-full">
      <Map
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        style={{ width: '100%', height: '100%' }}
      >
        <DeckGLOverlay layers={layers} />
      </Map>

      {/* Invalid Token Alert Overlay */}
      {(!MAPBOX_ACCESS_TOKEN || MAPBOX_ACCESS_TOKEN.includes('pk.eyJ1IjoiamF2aWVyc2VndXJh')) && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-50 bg-cyber-red/20 border border-cyber-red p-4 rounded backdrop-blur-md max-w-md text-center">
          <p className="text-cyber-red font-bold font-mono text-sm">CRITICAL SYSTEM ALERT: INVALID MAPBOX TOKEN</p>
          <p className="text-white/70 text-[10px] mt-2 font-mono uppercase">Please provide a valid VITE_MAPBOX_ACCESS_TOKEN in frontend/.env.local to activate global mapping.</p>
        </div>
      )}

      {isLoading && (
        <div className="absolute top-4 right-4 z-10 px-3 py-1 bg-surface-800/80 border border-cyber-blue/30 rounded flex items-center gap-2">
          <div className="w-2 h-2 bg-cyber-blue rounded-full animate-pulse" />
          <span className="data-ink text-cyber-blue">Uplink Active</span>
        </div>
      )}
      
      <div className="absolute bottom-4 left-4 z-10 bg-surface-900/50 backdrop-blur-sm p-2 panel-border rounded">
         <span className="data-ink">Zoom: {viewState.zoom.toFixed(1)}</span>
      </div>
    </div>
  );
};
