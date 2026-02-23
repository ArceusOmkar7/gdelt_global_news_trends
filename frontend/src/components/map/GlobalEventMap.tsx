import React, { useState, useMemo, useEffect } from 'react';
import Map from 'react-map-gl/mapbox';
import DeckGL from '@deck.gl/react';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { useQuery } from '@tanstack/react-query';
import { WebMercatorViewport } from '@math.gl/web-mercator';
import { useStore } from '../../store/useStore';
import { apiService } from '../../services/api';
import type { MapAggregation, Event } from '../../types';

const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

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

  // Update BBOX when viewState changes (debounced-like)
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

  const onViewStateChange = ({ viewState: nextViewState }: any) => {
    setViewState(nextViewState);
  };

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
      <DeckGL
        initialViewState={viewState}
        onViewStateChange={onViewStateChange}
        controller={true}
        layers={layers}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
      >
        <Map
          mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
          mapStyle="mapbox://styles/mapbox/dark-v11"
          reuseMaps
        />
      </DeckGL>

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
