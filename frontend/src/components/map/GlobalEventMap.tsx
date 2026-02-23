import React, { useState, useMemo, useEffect, useRef } from 'react';
import Map, { useControl } from 'react-map-gl/mapbox';
import type { MapRef } from 'react-map-gl/mapbox';
import { MapboxOverlay } from '@deck.gl/mapbox';
import type { MapboxOverlayProps } from '@deck.gl/mapbox';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import { ScatterplotLayer } from '@deck.gl/layers';
import { useQuery } from '@tanstack/react-query';
import { useStore } from '../../store/useStore';
import { apiService } from '../../services/api';
import type { MapAggregation, Event } from '../../types';

const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

function DeckGLOverlay(props: MapboxOverlayProps) {
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

  const mapRef = useRef<MapRef>(null);
  const [mapBBox, setMapBBox] = useState({ n: 90, s: -90, e: 180, w: -180 });

  // Helper to validate BBOX
  const isValidBBox = (bbox: any) => {
    return !Object.values(bbox).some(val => typeof val !== 'number' || isNaN(val));
  };

  useEffect(() => {
    const updateBBox = () => {
      const map = mapRef.current?.getMap();
      if (!map) return;

      const bounds = map.getBounds();
      if (!bounds) return;

      const nextBBox = {
        w: bounds.getWest(),
        s: bounds.getSouth(),
        e: bounds.getEast(),
        n: bounds.getNorth()
      };

      if (isValidBBox(nextBBox)) {
        setMapBBox(nextBBox);
        console.log('Map BBOX Updated:', nextBBox, 'Zoom:', viewState.zoom);
      } else {
        console.warn('Map BBOX calculation resulted in NaN, skipping update.');
      }
    };

    const timer = setTimeout(updateBBox, 300);
    return () => clearTimeout(timer);
  }, [viewState]);

  const { data: mapResponse, isLoading } = useQuery({
    queryKey: ['map-data', mapBBox, Math.round(viewState.zoom), dateRange, eventRootCode],
    queryFn: async () => {
      // Final guard against NaN in query
      if (!isValidBBox(mapBBox)) {
        console.error('Blocking API call due to invalid BBOX:', mapBBox);
        return { zoom: viewState.zoom, is_aggregated: true, count: 0, data: [] };
      }

      const res = await apiService.getMapData(
        mapBBox,
        viewState.zoom,
        dateRange[0],
        dateRange[1],
        eventRootCode
      );
      console.log('API Response:', res.count, 'items', 'Aggregated:', res.is_aggregated);
      return res;
    },
    placeholderData: (previousData) => previousData,
    staleTime: 1000 * 30,
  });

  const layers = useMemo(() => {
    if (!mapResponse || mapResponse.count === 0) return [];

    if (mapResponse.is_aggregated) {
      const aggData = mapResponse.data as MapAggregation[];
      return [
        new HeatmapLayer({
          id: 'heatmap',
          data: aggData,
          getPosition: (d: MapAggregation) => [d.lon, d.lat],
          getWeight: (d: MapAggregation) => d.intensity,
          radiusPixels: 60,
          intensity: 5,
          threshold: 0.005,
          colorRange: [
            [0, 243, 255, 0],
            [0, 243, 255, 100],
            [0, 243, 255, 150],
            [0, 255, 65, 200],
            [255, 255, 255, 255],
          ],
        }),
        new ScatterplotLayer({
          id: 'agg-points',
          data: aggData,
          getPosition: (d: MapAggregation) => [d.lon, d.lat],
          getFillColor: [0, 243, 255, 80],
          getRadius: 15,
          radiusMinPixels: 1,
          radiusMaxPixels: 3,
          pickable: false,
        })
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
          getRadius: (d: Event) => Math.max(10, d.num_mentions),
          radiusMinPixels: 4,
          radiusMaxPixels: 30,
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
      {/* Data Scanning Progress Bar */}
      {isLoading && (
        <div className="absolute top-0 left-0 w-full h-[2px] z-50 overflow-hidden bg-cyber-blue/10">
          <div className="h-full bg-cyber-blue animate-[progress_2s_infinite_linear]" 
               style={{ width: '30%', boxShadow: '0 0 10px #00f3ff' }} />
        </div>
      )}

      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        style={{ width: '100%', height: '100%' }}
      >
        <DeckGLOverlay layers={layers} />
      </Map>

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

      {mapResponse?.count === 0 && !isLoading && (
        <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-10 px-4 py-2 bg-surface-900/80 border border-white/10 rounded">
           <span className="data-ink text-white/50">NO SIGNAL DETECTED IN THIS SECTOR</span>
        </div>
      )}
      
      <div className="absolute bottom-4 left-4 z-10 bg-surface-900/50 backdrop-blur-sm p-2 panel-border rounded">
         <span className="data-ink">Zoom: {viewState.zoom.toFixed(1)} | Points: {mapResponse?.count || 0}</span>
      </div>
    </div>
  );
};
